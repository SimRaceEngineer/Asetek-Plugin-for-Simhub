//+------------------------------------------------------------------+
//| export_calendrier.mq5                                            |
//|                                                                  |
//| Exporte le calendrier economique de MetaTrader 5 en CSV.         |
//|                                                                  |
//| LECTEUR SEUL. Ce script ne contient AUCUNE fonction de trading : |
//| ni OrderSend, ni PositionOpen, ni PositionClose, ni modification |
//| de quoi que ce soit. Il lit le calendrier et ecrit un fichier    |
//| dans MQL5\Files\. C'est verifiable en relisant le code ci-dessous|
//| -- il fait 150 lignes.                                          |
//|                                                                  |
//| POURQUOI CE SCRIPT                                              |
//|                                                                  |
//|   Le paquet Python MetaTrader5 n'expose pas le calendrier. Il    |
//|   n'existe que cote MQL5. Or c'est la seule source qui donne a   |
//|   la fois l'HEURE et l'IMPORTANCE des publications, sur la meme  |
//|   horloge que les prix qu'on enregistre.                        |
//|                                                                  |
//| LE FUSEAU N'EST PAS SUPPOSE, IL EST MESURE                      |
//|                                                                  |
//|   Je ne sais pas avec certitude dans quel fuseau MT5 rend les    |
//|   heures du calendrier. Plutot que de deviner, le fichier        |
//|   commence par trois lignes de commentaire donnant TimeCurrent   |
//|   (heure serveur), TimeGMT et TimeLocal au moment de l'export.   |
//|   Il suffira de comparer une publication connue -- le CPI du     |
//|   12/08 a 14:30 heure de Paris -- a ce qui sort ici pour etablir |
//|   le decalage une fois pour toutes.                             |
//|                                                                  |
//| CE QU'IL ECRIT                                                  |
//|                                                                  |
//|   MQL5\Files\calendrier.csv, separateur point-virgule :         |
//|                                                                  |
//|   ts;pays;devise;evenement;importance;actual;forecast;previous   |
//|                                                                  |
//|   Les valeurs vides sortent vides, pas a zero : un actual absent |
//|   et un actual nul ne sont pas la meme chose, et les confondre   |
//|   fausserait toute mesure de surprise.                          |
//+------------------------------------------------------------------+
#property copyright "analyse ScalpEA"
#property version   "1.00"
#property script_show_inputs
#property strict

input datetime Debut    = D'2026.06.01 00:00';   // debut de l'export
input datetime Fin      = D'2026.10.01 00:00';   // fin de l'export
input string   Fichier  = "calendrier.csv";      // dans MQL5\Files\
input string   Pays     = "";                    // "" = tous, sinon "US"
input bool     ToutesImportances = true;         // false = HIGH seulement

//+------------------------------------------------------------------+
//| Les valeurs du calendrier sont stockees en entier multiplie par  |
//| un million, et LONG_MIN signifie ABSENT. Rendre 0 pour un champ  |
//| absent serait une erreur silencieuse : une surprise calculee sur |
//| un forecast absent vaudrait exactement l'actual.                 |
//+------------------------------------------------------------------+
string Valeur(long v)
  {
   if(v == LONG_MIN)
      return("");
   return(DoubleToString((double)v / 1000000.0, 6));
  }

//+------------------------------------------------------------------+
string Importance(ENUM_CALENDAR_EVENT_IMPORTANCE imp)
  {
   switch(imp)
     {
      case CALENDAR_IMPORTANCE_LOW:      return("LOW");
      case CALENDAR_IMPORTANCE_MODERATE: return("MODERATE");
      case CALENDAR_IMPORTANCE_HIGH:     return("HIGH");
      default:                           return("NONE");
     }
  }

//+------------------------------------------------------------------+
//| Le point-virgule est le separateur du fichier : s'il apparait    |
//| dans un nom d'evenement, il decale toutes les colonnes suivantes.|
//| On le remplace, et on remplace aussi les retours a la ligne.     |
//+------------------------------------------------------------------+
string Propre(string s)
  {
   StringReplace(s, ";", ",");
   StringReplace(s, "\n", " ");
   StringReplace(s, "\r", " ");
   return(s);
  }

//+------------------------------------------------------------------+
void OnStart()
  {
   MqlCalendarValue valeurs[];
   string pays = (StringLen(Pays) > 0) ? Pays : NULL;

   int n = CalendarValueHistory(valeurs, Debut, Fin, pays, NULL);
   if(n <= 0)
     {
      PrintFormat("KO : CalendarValueHistory rend %d, erreur %d.",
                  n, GetLastError());
      Print("Verifier que le calendrier est active dans le terminal");
      Print("(Outils > Options > Serveur > Actualites) et que la");
      Print("plage de dates n'est pas vide.");
      return;
     }

   int h = FileOpen(Fichier, FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(h == INVALID_HANDLE)
     {
      PrintFormat("KO : impossible d'ecrire %s, erreur %d.",
                  Fichier, GetLastError());
      return;
     }

   // Le fuseau, mesure et non suppose. Ces trois lignes permettront
   // d'aligner le calendrier sur les cycles sans rien deviner.
   FileWrite(h, StringFormat("# TimeCurrent (serveur) = %s",
                             TimeToString(TimeCurrent(),
                                          TIME_DATE | TIME_SECONDS)));
   FileWrite(h, StringFormat("# TimeGMT             = %s",
                             TimeToString(TimeGMT(),
                                          TIME_DATE | TIME_SECONDS)));
   FileWrite(h, StringFormat("# TimeLocal (machine) = %s",
                             TimeToString(TimeLocal(),
                                          TIME_DATE | TIME_SECONDS)));
   FileWrite(h, "# les heures ci-dessous sont celles rendues par");
   FileWrite(h, "# CalendarValueHistory, telles quelles, sans conversion");
   FileWrite(h, "ts;pays;devise;evenement;importance;actual;forecast;previous");

   int ecrits = 0;
   int sautes = 0;
   for(int i = 0; i < n; i++)
     {
      MqlCalendarEvent ev;
      if(!CalendarEventById(valeurs[i].event_id, ev))
        {
         sautes++;
         continue;
        }
      if(!ToutesImportances && ev.importance != CALENDAR_IMPORTANCE_HIGH)
         continue;

      MqlCalendarCountry pa;
      string code = "";
      string devise = "";
      if(CalendarCountryById(ev.country_id, pa))
        {
         code = pa.code;
         devise = pa.currency;
        }

      FileWrite(h, StringFormat("%s;%s;%s;%s;%s;%s;%s;%s",
                                TimeToString(valeurs[i].time,
                                             TIME_DATE | TIME_MINUTES),
                                code, devise,
                                Propre(ev.name),
                                Importance(ev.importance),
                                Valeur(valeurs[i].actual_value),
                                Valeur(valeurs[i].forecast_value),
                                Valeur(valeurs[i].prev_value)));
      ecrits++;
     }

   FileClose(h);
   PrintFormat("%d evenement(s) lus, %d ecrits, %d sautes (evenement "
               "introuvable).", n, ecrits, sautes);
   PrintFormat("Fichier : MQL5\\Files\\%s", Fichier);
   Print("Aucune position n'a ete ouverte, modifiee ou fermee : ce");
   Print("script ne contient aucune fonction de trading.");
  }
//+------------------------------------------------------------------+
