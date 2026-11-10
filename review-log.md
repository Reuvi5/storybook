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
