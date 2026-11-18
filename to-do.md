# To do

Real defects and risks, most important first. From review runs 1–3 (see `review-log.md`) and from using the live site.

## Speed
1. **Upload to PDF has no margin under 60 seconds.** Run 2: 59 s. The page check is stricter since Nov 17 (it counts arms and compares the face with a close-up), so more pages get redrawn, and one redraw adds about 20 s. Render's free server has 0.1 CPU and sleeps when idle (UptimeRobot keeps it awake). Options: smaller reference pictures, a paid instance, or a slightly looser face score if redraws become common.

## The pictures
2. **Jack and the Beanstalk hasn't been checked on the new code.** The stand-in-face blur and the arm check were only seen on a Red Riding Hood book (run 3, all pages fine). Make one Jack book and check pages 1, 10 and 20 against the About Me cartoon.
3. **The stand-in's head is found by a vision call, once per scene** (saved as `HEAD#nn`). If a box is wrong, that page falls back to the old way and can drift a little toward the stand-in. Look at the `hero_head_found` lines in the logs once, and redo any box that isn't on the head.
4. **OpenAI's safety filter blocks some drawings.** Jack's mother's character sheet had to be copied out of a finished scene, and single page drawings are sometimes blocked. A blocked drawing counts as one of the 3 tries.
5. **The story text says "someone" and "them".** It fits any child, but with a girl in a dress, "she" would read more naturally. Possible: pick the pronoun from the photo or ask in the form.

## Printing
6. **No sandbox order has been placed on the live site yet.** The flow was tested locally, and the real Lulu sandbox returned the cover size and a quote ($21.99 for printing, shipping, fulfillment and tax to North Carolina), but no print job has been created from the live site. Place one and check that the Orders page shows Lulu's status.
7. **US addresses only, one shipping speed (MAIL).** Faster shipping or other countries would need a price per shipping level; the margin guard refuses any address whose quote leaves less than $5.
8. **The approval preview uses the browser's PDF viewer.** Some phones show a blank frame; the "Open" link works everywhere. A page-by-page image preview would be clearer.

## Money
9. **A digital book makes about $0.20** ($0.99 price, about $0.70 to make, about $0.09 of Stripe fees). A book with several redraws can cost close to $0.99. The printed book is where the margin is ($10.99 per copy, see `WRITEUP.md`).
10. **Sales tax is Lulu's estimate for the address**; it varies by state and is inside the flat $34.99, so the margin varies by a dollar or two.

## Keys and accounts
11. **The OpenAI key expired on Nov 17** and every book failed with "we couldn't check the details" until it was replaced. Keys now need renewing; the error message should say the picture service is down, not point at the name field.

## Smaller things
12. The hourly limit (3 books an hour per account) gets in the way of testing.
13. The About Me page prints only what was entered; with no details it is just the name and the two pictures.

## Done since the last list
- Names typed in lowercase are capitalized (run 3 found "deens" on the cover).
- Pages no longer copy the stand-in's face, and the page check counts arms (the 3-armed Red Riding Hood page).
- Red Riding Hood wears a dress (girls).
- Clicking a page opens it large, as printed, instead of the bare picture.
- `to-do.md` committed with the real list (run 2's first fix).
- Phone layout: no sideways scrolling on any page at 400 px.
