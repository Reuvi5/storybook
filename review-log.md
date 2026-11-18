# Review log

Every run of the `storybook-review` rubric against the live site, oldest first. Entries are only ever
appended, never edited.

## Run 1 — 2026-11-10 — reviewer: self (Claude, with the builder signing in and paying) — browser: Claude's built-in browser
Total 86 (first run)
PDF 36/40 · UI 19/20 · Money 20/20 · Engineering 11/20
Upload 18:15:37 → PDF never (Red Riding Hood: server died in the PDF stage; finished only by "Try again" at 18:41:06, after a fix was deployed)
Upload 18:51:39 → PDF 18:52:43 (64 s; the app reports 63 s) — Jack and the Beanstalk, after the fix
Balance: 9.01 → fund 14.01 → Red Riding Hood 13.02 → failed Jack book (refunded) 13.02 → Jack 12.03 → refund 7.03 → refund 2.03 → refund 0.00
Avg cost per book: $0.699 over 1 book (price $0.99). The cost counter was reset at 18:49 UTC, after the crash lost the Red Riding Hood book's cost.
Not measured: none
Photos: Red Riding Hood used a photo not used in development (meira). The Jack book used a photo of "yisroel", which may have been used in development; rerun Jack with a new photo next time.
Changed since run 1: (first run). Two fixes were deployed DURING this run, after the defects below were found: 13:40 local (PDF embeds JPEGs directly, memory cut from ~470 MB to ~90 MB per book) and 13:50 local (failure messages, costs saved per stage, honest timing after a retry).

Evidence by section
- PDF: both PDFs have 22 pages (cover, 20 story pages, About Me) at 432x648 pt; same template and text panels in both. Same child on Jack pp. 2, 11, 21 and Red pp. 2, 11, 21 (curly hair and kippah / bows and red cape), one cartoon style throughout. All text is real type (Times-Bold, Helvetica; checked at 400% on Jack p. 6 and Red p. 18). No text over a face anywhere. Text over things the page needs: Jack p. 17 (story p. 16) — the panel covers Jack's body and the base of the harp; Red p. 16 (story p. 15) — the panel covers Red's legs and cape. On both pages the top third is empty wall. About Me shows the name and every detail entered (age 10, Green, Pizza, Owl, about text) with the real photo beside the cartoon.
- UI: landing page loaded in 0.33 s (DOMContentLoaded 0.17 s). Numbered 3-step form. Progress bar names the stage ("Creating your character", "Drawing your 20 pages", "Putting your book together"). Thumbnails appeared one by one (Jack book: 1 → 2 → 14 → 21). Balance shown in the header on every page. Usable at 400 px (no horizontal scroll on the New book, book, or Wallet pages; the history table is 6 px wider than its card). Empty balance: the Make button is replaced by "Each book costs $0.99. Your balance is $0.00. Add funds", and the server refuses with "Each book costs $0.99, and your balance is $0.00. Add funds in your Wallet first." Failure messages were wrong before the 13:50 fix: the out-of-credits failure at 18:44 said "we couldn't create a character from this photo", and the crashed book said "0 pictures didn't come out". My books still shows "Drawing..." on the failed book's card.
- Money: funding +$5.00 exactly (9.01 → 14.01, Stripe pi_3UaJYSD77uFrOgI50oHUNYXZ). Each book -$0.99 exactly. The failed book was refunded +$0.99 automatically. Refund requested and processed (re_3UaJYSD77uFrOgI50jKthk5S), balance 12.03 → 7.03; refunds are capped at unspent money (the last one was $2.03). Every entry shows cause, amount, timestamp and running balance; the history adds up to $0.00. The Wallet shows the average API cost per book ($0.699) next to the $0.99 price, with image calls, retries and checks counted.
- Engineering: Upload to PDF was over 60 s both times (see clock readings). Signed out and back in at 18:54; the Red Riding Hood PDF downloaded again at 18:55:01 (7,260,221 bytes). The character bible is in DynamoDB (`STORY#jack` / `STORY#red`, `BIBLE#…` records with S3 images); `python prepare_story.py all --sheet` reads it back. Attempt counts show on every image ("Drawing · try 1 of 3", "Redrawing · try 2 of 3", "Passed on try 2 of 3"), but Red pp. 16 and 18 read "None passed · best of 2", which contradicts the cap of 3 (a blocked drawing wasn't counted; fixed at 13:40). `to-do.md` still describes the old 3-page book. `review-log.md` is created by this run. Repo: 7 commits, no keys in any file or in history (only `.env.example`, with placeholders).

Fix first:
1. Upload to PDF takes over 60 s (Jack 64 s; Red Riding Hood never finished on the old code) (engineering, -6). The character alone takes ~25 s and the pages ~35 s. Start the pages while the character is being checked, send smaller reference pictures, and consider a paid Render instance (the free one has 0.1 CPU).
2. Text covers part of the story on Jack p. 17 (story p. 16, Jack's body and the harp) and Red p. 16 (story p. 15, Red's legs), while the top third of both pages is empty wall (PDF, -4). The checker judges a whole 28%-high band, not the panel's actual size. Judge the actual panel area, and score candidate spots by how busy the picture is there.
3. `to-do.md` describes the 3-page book, not the real defects of this one (engineering, -2).
4. Attempt label "None passed · best of 2" on Red pp. 16 and 18 contradicts the 3-try cap (engineering, -1). Fixed at 13:40; verify in run 2.
5. Failure messages: the out-of-credits failure blamed the photo, the crashed book said "0 pictures didn't come out" (fixed 13:50, verify in run 2), and My books still shows "Drawing..." on a failed book (UI, -1).


## Run 2 — 2026-11-10 — reviewer: self (Claude, with the builder signing in and paying) — browser: Claude's built-in browser
Total 96 of the 98 points measured (was 86). The builder scoped this run to Jack and the Beanstalk; phone width wasn't measured (the computer disconnected).
PDF 40/40 · UI 18/18 measured (phone width, 2, not measured) · Money 20/20 · Engineering 18/20
Upload 19:57:49 → PDF ready 19:58:48 by the app's own clock ("made in 59 seconds"); the Download button was showing at my next check, 19:58:55. Jack, new photo, 21 pictures, 1 redraw.
Balance: 0.00 → fund 5.00 → generate 4.01 → refund 0.00
Avg cost per book: $0.700 over 2 books (price $0.99)
Not measured: usable at about 400 px (2 pts; the computer disconnected mid-check; it passed in run 1, and the Wallet table fix from run 1 was deployed). Red Riding Hood wasn't regenerated (the builder chose Jack only); its existing PDF was re-laid out and checked.
Changed since run 1:
- Text placement now measures how plain each spot is. Text never goes on busy areas, and false face boxes over plain sky are ignored.
- Text spots are checked at the panel's real size.
- No more shrunk "band" pages.
- The pages start while the character is still being checked.
- Failure messages name the real cause; costs are saved after each stage; timing is honest after a retry.
- My books says "Couldn't be made" on failed books, and an empty balance shows the balance message before the hourly limit.
- A free re-layout rebuilds older books with the current rules.

Evidence by section
- PDF: new Jack book (Test Reader) has 22 pages: cover, 20 story pages and About Me. The re-laid-out Jack (yisroel) and Red Riding Hood (meira) books have 22 pages each, on the same template (same cover, panels and About Me layout). All three were checked page by page: full-page art on every page, and no text over any face, character or object the page needs. Run 1's problem pages are fixed: Jack p. 16 and Red p. 15 now have their text on the empty wall at the top. Same child on new Jack pp. 2, 11 and 21, and one cartoon style throughout. The text is real type (Times-Bold, Times-Italic, Helvetica, Helvetica-Bold embedded; no lettering in the pictures). The smallest text is 13 pt (re-laid-out Jack pp. 9 and 12), still legible. About Me shows "Test Reader", age 9, Blue, Pancakes, Dolphin and the about text, with the real photo beside the cartoon.
- UI: My books loaded in 0.52 s. Progress named each stage ("Creating your character", "Drawing your 20 pages", "Putting your book together") and showed the attempt on every picture ("Checking · try 1 of 3", "Redrawing · try 2 of 3", "Passed on try 1 of 3"). Thumbnails appeared as each finished (1 → 13 → 21 of 21). The balance is in the header. History is readable. Empty balance: the Make button is replaced by "Each book costs $0.99. Your balance is $0.00. Add funds", and the server refuses with "Each book costs $0.99, and your balance is $0.00. Add funds in your Wallet first." A failed book's card now says "Couldn't be made".
- Money: fund +$5.00 (pi_3UaL1eD77uFrOgI51zlwTvPx), 0.00 → 5.00. Book -$0.99, 5.00 → 4.01. Refund of $4.01 requested and processed (re_3UaL1eD77uFrOgI51hq71cIT), 4.01 → 0.00. The history adds up: +5.00 -0.99 -4.01 = 0.00. The Wallet shows the average API cost per book ($0.700 over 2 books: 42 image calls, 2 retries, 42 checks) next to the $0.99 price.
- Engineering:
  - Speed: 59 s by the app (from book creation to PDF saved); my own stopwatch reading falls between 59 and 66 s, because I checked every 8 s. No margin.
  - Persistence: books made at 18:15 and 18:51 downloaded at 19:55 in a session that started with a sign-out and sign-in at 18:54.
  - Character bible: in DynamoDB (`STORY#jack` / `BIBLE#…`).
  - Regeneration loop: the attempt count shows on every tile, capped at 3; "None passed · best of 3" has not been seen live.
  - Repo: 11 commits, no keys anywhere in its history. `review-log.md` holds run 1. `to-do.md` in the repo still describes the old 3-page book (-2).

Fix first:
1. Commit the updated `to-do.md`: the repo still has the 3-page list (engineering, -2).
2. Speed has no margin: 59 s by the app, and a slow OpenAI response or one more redraw goes over 60 (engineering, 6 at risk). Send smaller reference pictures (cuts time and cost), or move to a paid Render instance (the free one has 0.1 CPU).
3. Re-check phone width (400 px), which wasn't measured this run (UI, 2 not measured).
4. Make one Red Riding Hood book with an unused photo before the instructor does: this run checked only Jack end to end.
5. Two re-laid-out Jack pages (9, 12) use 13 pt text to fit a clear spot; fine, but the smallest in the book (PDF, 0 now).

## Run 3 — 2026-11-17 — reviewer: self (Claude) — browser: none (desk review of the builder's new book)
Total: not produced. This run reviewed the PDF and the repo only, so per the rubric no total is given.
Measured: PDF 40/40 · Money 3/3 of the desk lines · Engineering 7/7 of the desk lines · UI not measured
Upload → PDF: not measured (the builder made the book; the PDF was built 2026-11-17 18:42:31 UTC by its own metadata)
Balance: not measured
Avg cost per book: not measured this run (run 2: $0.700 over 2 books, price $0.99; the Wallet still shows it, code unchanged)
Not measured: every [browser] line — UI 20, Money 17 (fund, deduct $0.99, refuse when short, refund, history), Engineering 13 (under 60 s, sign out and back in, attempt count visible) — and the history-reconciles line (1). Jack and the Beanstalk was not regenerated, so the two-PDF lines are judged on the new Red Riding Hood book plus the shared code.
Photo: a child not used in development ("deens").
Changed since run 2:
- It's a real book now: front cover ("starring" the name), a copyright page (© 2026 Kupchik Games, publisher, edition, book ID), 20 story pages starting right after it, "The End", and an About Me back cover. 24 pages in all.
- Print and ship through Lulu's print API (sandbox only): the user approves the exact print files, then enters a US address; the order is quoted, charged ($34.99), and refunded automatically if Lulu rejects it.
- The name and About Me details are checked before anything is charged or printed (rules, OpenAI moderation, and a GPT check for insults and fake names).
- Pages no longer copy the stand-in's face: her head is blurred out of each pre-drawn scene before the child is drawn in. The page check now counts the hero's arms and compares the face with a close-up of the child's cartoon.
- Red Riding Hood wears a dress (girls) under the cape.
- New kid-friendly design across the site, and a page reader (click a page to see it large, as printed).
- Names typed in lowercase are capitalized (fixed after this run's finding below).

Evidence by section
- PDF (Little Red Riding Hood, starring deens; 24 pages at 432 x 648 pt): p. 1 front cover with title, the cartoon and "starring deens"; p. 2 copyright page; pp. 3–22 the 20 story pages, in order and complete (the text runs from "Once upon a time…" to "…never strayed from the path again."); p. 23 The End; p. 24 About Me with the real photo, the cartoon and the name. The hero is the same child on every page she appears (pp. 3–9 and 14–22; pp. 10–13 are the wolf and Grandmother alone, as the story says), and she matches the cover and the About Me cartoon: same long dark wavy hair with a center part, green eyes, and small earrings. That was run 2's open problem (pages consistent with each other but not with the cartoon) and it is fixed. One cartoon style throughout; the same Mother (pp. 4, 22), Grandmother (pp. 12, 20, 22), wolf and woodcutter (pp. 19, 20, 22). The dress shows on all 16 hero pages. No extra or missing arms or hands on any page (checked every hero page at 110 dpi; p. 15, hand on chin, has two arms). Text never covers a face or anything the page needs: 16 panels on plain sky or wall at the top, 4 at the bottom on the ground or path below the characters (pp. 3, 10, 11, 21), checked on all 20 pages. The text is real type (Times-Bold and Times-Italic embedded, extractable), legible at 100%; p. 21 uses a dark panel over the sunset path.
- Money (desk): the average API cost per book is tracked per call (images, redraws, checks, detail checks) and shown on the Wallet next to the $0.99 price (`ai.Meter`, `generator.cost_stats`, `wallet.html`); the print price ($34.99) is shown next to Lulu's average cost.
- Engineering (desk): the character bible is in DynamoDB (`STORY#red` / `BIBLE#…`, now also `HEAD#…` for the stand-in head boxes). `to-do.md` is updated in this commit with the real open defects. `review-log.md` holds runs 1–3, oldest first, none edited. Repo: 18 commits; no API key in any file or anywhere in the history (only `.env.example`, with placeholders).

Fix first:
1. The name prints exactly as typed, so a lowercase "deens" went on the cover, copyright page, The End and About Me (PDF, 0 points but the first thing a parent sees). Fixed after this run: names typed all in lowercase are capitalized; names with a capital are left as typed.
2. Run the browser half of the rubric before the instructor does: speed (59 s in run 2, no margin, and the stricter page check can add a redraw), fund/deduct/refund, phone width (UI 2, unmeasured since run 1) (up to 50 points unmeasured).
3. Make one Jack and the Beanstalk book on the new code: the face blur and arm check were only seen on Red Riding Hood.
4. Place one sandbox print order on the live site end to end and check the Orders page (the flow is tested locally with Lulu's real quote, not yet on the live site).
