# Why audio description, and what good looks like

Research notes, collected 2026-10-19. For each source we say how much of it we actually read.

## The need

- **Premier League and Microsoft** announced a five-year partnership on 30 June / 1 July 2025: Microsoft is the league's official cloud and AI partner, for 1.8 billion fans in 189 countries. The showcase is a Copilot-powered Premier League Companion. Features described as coming include more translation and subtitling and **audio summaries**. ([Microsoft Source](https://news.microsoft.com/source/2025/07/01/premier-league-and-microsoft-announce-five-year-strategic-partnership-to-personalize-the-fan-experience-with-ai-for-1-8-billion-people/), [Microsoft Source EMEA](https://news.microsoft.com/source/emea/features/premier-league-microsoft-partnership/); from search summaries, not read in full.)
- **Sky Sports** announced on 8 October 2026 (World Sight Day), starting 10 October, live subtitles on about 210 Premier League games a season and **live descriptive audio commentary on about 109**, about one match a day in each game week, in the style of radio commentary and developed with the RNIB. ([What Hi-Fi](https://www.whathifi.com/streaming-entertainment/tv-streaming-services/sky-announces-a-significant-step-forward-for-its-accessible-premier-league-coverage-and-its-a-promising-move), [ISPreview](https://www.ispreview.co.uk/index.php/2026/10/sky-sports-to-introduce-live-subtitles-and-live-descriptive-audio-commentary.html); news reports of the announcement.)
- **Clubs** run audio-described commentary mostly with volunteers. A 2026 case study of Bohemians FC (Dublin, in-stadium since 2019) says ADC "describes action rather than just commenting on it", is "transformative" for some users, and that take-up overall is low. ([Journal of Specialised Translation](https://www.jostrans.org/article/view/5620); abstract only, the PDF could not be read.)
- **FIFA** will offer audio-descriptive commentary for all World Cup 2026 matches. ([FIFA](https://inside.fifa.com/news/accessibility-world-cup-2026-disability-social-inclusion); search summary.)
- **Microsoft** itself: Seeing AI and OneCourt (a tactile tablet "powered by Microsoft Azure") at a World Cup match in Seattle. The blind fan quoted wanted to know "what team is attacking, what team has the ball, what team took a shot", and to feel where the ball is. ([FOX 17](https://fox17.com/news/nation-world/microsofts-seeing-ai-and-onecourt-help-blind-fans-experience-world-cup-action-soccer-match-seattle-social-media-technology-artificial-intelligence-disability-phone-camera-audio-stadium-seat-concession-data-score); read in full.) One person's account, not a survey.

## Style guidance we found

- **RNIB and British Blind Sport**, guidance for clubs after focus groups: audio description is one of five areas; use **one commentator who purely describes the events on the pitch**, not a pundit; broadcast principles stress clear description, context, and following the action, atmosphere and pace. ([guidance PDF](https://media.rnib.org.uk/documents/SSD_-_Accessible_Stadiums_BP_Guidance.pdf), [RNIB football broadcast research](https://www.rnib.org.uk/professionals/research-and-data/reports-and-insight/accessibility-of-football-broadcasts-on-tv-research-report/); read through search summaries only.)

## Design rules we took from it (our interpretation, not RNIB's words)

1. **Describe, do not comment.** Present tense, facts, no opinion or prediction. The templates and the verifier enforce this.
2. **Say who has the ball, where it is going, and the score.** Every description names the team and player; goals and half-time repeat the score; the score is repeated every ten minutes.
3. **Orientation first.** Kick-off says which way each team attacks. Directions are given from the attacker's point of view ("down the left").
4. **Fit the gaps.** Speech must not run over the next important moment: a planner places sentences into the silence, shortens them, or drops them, and never drops a goal.
5. **Let the sound carry position.** A stereo ball sound moves with the ball so the voice does not have to repeat positions.
6. **Offer control.** Detail level, speed, language, and a calm mode, because listeners differ.
7. **Be honest about checking.** Every sentence is verified against the events before it is spoken; template text takes over when a model cannot pass.

## What we have not done

- No blind or low-vision listener has tested SoundPitch. The style choices above come from public guidance and are unvalidated.
- The voices are the browser's or Azure neural voices, not trained audio describers.
- Synthetic data has no real positions on the pitch beyond what the generator invents, so the spatial description is plausible, not measured.
