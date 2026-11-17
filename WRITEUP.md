# Make it a real book — write-up

Live site: https://storybook.kupchikgames.shop · Repo: https://github.com/Reuvi5/storybook

## What I built

**A real book.** Every book now has this order:
- A front cover with the title and "starring" the child's name.
- A copyright page with © year, "Kupchik Games" as the publisher, the website, an edition line and the book ID.
- The story, starting on the first page after the copyright page (20 pages), then "The End".
- An About Me back cover with the child's photo, their cartoon self, name, age and details.

**Print files.** When someone orders a printed copy, the app builds the two files the printer needs:
- **Inside pages:** 6 × 9 in with 0.125 in bleed, and all text kept 0.5 in inside the trim. They're padded with endpapers up to Lulu's 24-page hardcover minimum.
- **Cover:** one piece, back cover + spine + front cover, at the exact size Lulu returns for that page count. Lulu returned 14.00 × 10.75 in for 24 pages.

**Print and ship (Lulu Print API, sandbox only).**
- *Review and approve:* the user sees the exact cover and inside-page PDFs the printer will get, then ticks "I approve". The approval is tied to a fingerprint of those two files: if either changes, they have to approve again. The address form stays locked until then.
- *Order:* the user enters a US address, which is validated (state, 5-digit ZIP, phone, email). The app asks Lulu for a quote, charges the wallet and creates the Lulu print job. If Lulu rejects the job, the money is refunded automatically.
- *Track:* an Orders page shows each order's Lulu status and tracking.
- *Sandbox only:* the code refuses any Lulu address that isn't the sandbox, and the keys live only in `.env` and on Render.

**Checking what the child types.** The name and every About Me field go through three checks before anything is charged:
1. Rules:
   - The name has to be letters in any script, at most 4 words, with no repeated junk.
   - Words like "test" and "asdf" are blocked.
   - Age has to be a number.
   - No phone numbers, emails, links or street addresses (a privacy check).
2. OpenAI's moderation model.
3. A short GPT check that the name is a real-sounding name and not an insult or epithet, and that each detail is fine for a children's book.

If a check can't run, the book is refused rather than printed unchecked. Each error shows under the field it belongs to.
- *Pass:* "Sarah", "José María", "Zoë O'Brien-Smith" and "李明".
- *Rejected:* "Stupid", "Big Loser", "asdf", "Bob123", a phone number and a link.

## Business model

Two products, paid from a prepaid wallet that's topped up with Stripe:

1. **The digital book, $0.99.** You get the personalized 24-page PDF in under a minute. It's close to break-even, and it works as the preview: parents see the whole book before paying for paper.
2. **The printed hardcover, $34.99, shipping included.** One flat price, with no shipping surprise at checkout. This is where the money is made.

## Cost per printed book

The Lulu numbers are a real sandbox quote (`python lulu_check.py`) for a 6 × 9 full-color premium hardcover with 24 pages, shipped by MAIL to a North Carolina address.

| | Cost |
|---|---:|
| Generation (OpenAI: images, quality checks, input checks), average per book | $0.70 |
| Lulu printing | $14.01 |
| Lulu shipping (MAIL) | $5.69 |
| Lulu fulfillment | $0.75 |
| Sales tax (varies by state) | $1.54 |
| Stripe fee on $34.99 (2.9% + $0.30) | $1.31 |
| **Total cost** | **$24.00** |
| **Price** | **$34.99** |
| **Margin** | **$10.99 (31%)** |

This count is on the cautious side. The $0.70 of generation was already paid by the $0.99 digital book. The Stripe fee here assumes the $34.99 came in as its own card payment; a larger wallet top-up splits the 30¢ across more purchases.

**Why $34.99:** after Lulu's $21.99 there has to be room for the card fee and the AI cost and still a real profit per order. $34.99 leaves about $11. Below roughly $30 the margin drops under $6, and one expensive address (Alaska, Hawaii, faster shipping) would erase it.

**Protection:** Lulu quotes every order before the user is charged. If the quote leaves less than $5 of margin (`PRINT_MIN_MARGIN_USD`), the order is refused and nothing is charged. The Wallet page shows the average Lulu cost over real orders next to the $34.99 price. The book page shows the AI cost per book next to the $0.99 price.

**Digital book math:** $0.99 − $0.70 generation − about $0.09 of Stripe fee (a $5 top-up costs $0.45 and covers 5 books) leaves about $0.20 per book.

## Carried over

Everything from "Charge for the book" still works:
- The wallet with a Stripe test-mode top-up, $0.99 per book, refunds and the history.
- The cost tracking.
- The shared 20-page template.
- The quality loop with up to 3 tries.
- Under 60 seconds.

The review was rerun and appended to `review-log.md`.
