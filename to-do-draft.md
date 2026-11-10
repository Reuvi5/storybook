# To do

Real defects, most important first. Found by using the live site and by review run 1 (see `review-log.md`).

## Speed
1. **Upload to PDF is right at the 60-second limit.** Run 1: the Jack book took 64 s (character about 25 s, pages about 35 s, the PDF under 1 s). The pages now start while the character is still being checked, which should save about 5 s, but one redrawn page still adds about 20 s. Render's free server has a tenth of a CPU; a paid instance would give some margin.
2. **The first Red Riding Hood book crashed the server while building the PDF** (the PDF library re-encoded every picture into raw pixels: about 470 MB on a 512 MB server). Fixed by embedding the JPEGs directly. Watch the Render logs for "Out of memory" anyway.

## The pictures
3. **Text covered part of the story on 2 pages** (Jack p. 16: Jack's body and the harp; Red p. 15: Red's legs) while the top of both pages was empty. The layout now measures how plain each spot is and never puts text over a busy area. Check every page of the next two books.
4. **The character isn't always the same person as the photo.** In run 1 the cartoon looked younger than the age entered (10). Faces stay consistent from page to page, but "looks like the photo" depends on the first drawing.
5. **OpenAI's safety filter blocks some drawings:** Jack's mother's character sheet was blocked on every wording and had to be copied out of a finished scene, and single page drawings are sometimes blocked. A blocked drawing counts as one of the 3 tries.

## Money
6. **A book costs about $0.70 to make and sells for $0.99.** A book with several redraws can cost close to $0.99. Smaller reference pictures would cut the cost of every page.
7. **The cost of the first Red Riding Hood book was lost** when the server crashed (costs were only saved at the end). Costs are now saved after each stage; the running average was reset at 18:49 UTC on Nov 10.

## Smaller things
8. "Try again" after a crash only rebuilds the PDF; its message used to say "0 pictures didn't come out". Fixed, but not yet seen on the live site.
9. Running out of OpenAI credits made the book say "we couldn't create a character from this photo". It now says the picture service is unavailable. Not yet seen live.
10. My books showed "Drawing..." on a failed book's card. Fixed: it now says "Couldn't be made".
11. The Wallet history table was 6 px wider than its card at 400 px.
12. The hourly limit (3 books an hour) gets in the way of testing, and a user with no money used to see the limit message instead of "add funds". Fixed.
