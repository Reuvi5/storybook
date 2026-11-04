# Setup: Google sign-in, AWS storage, Render

Every secret below goes in **`.env`** on your computer and in **Render → your service →
Environment** for the live site. Never in the code, never in the repo, never in Slack.

---

## 1. Google sign-in (about 10 minutes)

1. Go to **console.cloud.google.com** and sign in with your Google account.
2. Create a project: click the project picker at the top → **New project** → name it
   `storybook` → **Create**, then make sure it's selected.
3. Open **APIs & Services → OAuth consent screen** (in newer consoles this is called
   **Google Auth Platform**).
   - User type / Audience: **External**.
   - App name: `Jack and the Beanstalk Storybook`. Support email and developer contact: your email.
   - Scopes: you don't need to add any. The app only asks for `openid`, `email` and `profile`.
4. **Publish the app** (Audience → **Publish app**, or "Publishing status: In production").
   While it's in "Testing", only Google accounts you list as test users can sign in, and
   **your teacher couldn't sign in**. With only the basic scopes above, Google doesn't
   require verification to publish.
5. Create the credentials: **Credentials → Create credentials → OAuth client ID** (or
   **Clients → Create client**).
   - Application type: **Web application**. Name: `storybook`.
   - **Authorized redirect URIs**. Add all three:
     - `http://localhost:5001/auth/callback`
     - `https://storybook.kupchikgames.shop/auth/callback`
     - `https://YOUR-SERVICE.onrender.com/auth/callback` (your Render address)
   - Click **Create**, then copy the **Client ID** and **Client secret**.
6. Put them in `.env` (and later in Render):
   ```
   GOOGLE_CLIENT_ID=....apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=....
   ```
7. Also add a session secret, a long random string that signs the login cookie. Make one with:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   ```
   FLASK_SECRET_KEY=the-string-it-printed
   ```

If you get **"redirect_uri_mismatch"** when signing in, the address you're on isn't in the
list from step 5 exactly (check `http` vs `https`, the port, and no trailing slash).

---

## 2. AWS storage (about 15 minutes)

The app stores each book's record in a **DynamoDB** table and its images in a private
**S3** bucket. At this scale both cost effectively nothing (and fall within AWS's free tier),
but set a billing alert anyway (step 5).

Use the **us-east-1 (N. Virginia)** region for everything (top-right region menu in the AWS console).

### 2a. S3 bucket (the images)
1. AWS console → **S3** → **Create bucket**.
2. Bucket name: something unique, e.g. `kupchik-storybook-images`.
3. Keep **Block all public access** turned **on**. The app shows images through temporary
   private links, so the bucket never needs to be public.
4. **Create bucket**.

### 2b. DynamoDB table (the books)
1. AWS console → **DynamoDB** → **Create table**.
2. Table name: `storybook`
3. Partition key: `user_id` (String). Sort key: `sk` (String).
4. Table settings → **Customize settings** → Capacity mode: **On-demand**.
5. **Create table**.

### 2c. An access key just for this app
1. AWS console → **IAM** → **Users** → **Create user** → name `storybook-app` → don't give it
   console access → **Next** → **Attach policies directly** → don't tick anything → **Create user**.
2. Open the user → **Permissions** → **Add permissions → Create inline policy** → **JSON**, and
   paste this (replace `YOUR-BUCKET` with your bucket name, twice):
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:Query"],
         "Resource": "arn:aws:dynamodb:us-east-1:*:table/storybook"
       },
       {
         "Effect": "Allow",
         "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
         "Resource": "arn:aws:s3:::YOUR-BUCKET/*"
       },
       {
         "Effect": "Allow",
         "Action": ["s3:ListBucket"],
         "Resource": "arn:aws:s3:::YOUR-BUCKET"
       }
     ]
   }
   ```
   Name it `storybook-access` → **Create policy**. This key can only touch that one table and
   that one bucket, nothing else in your AWS account.
3. Same user → **Security credentials** → **Create access key** → "Application running outside AWS"
   → **Create**. Copy the **Access key ID** and **Secret access key** (the secret is shown only once).

### 2d. Add to `.env` (and later Render)
```
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
DYNAMODB_TABLE=storybook
S3_BUCKET=kupchik-storybook-images
```
When `S3_BUCKET` and `DYNAMODB_TABLE` are set, the app uses AWS. Without them it saves books in
a local `local_data/` folder (fine for testing; `local_data/` is in `.gitignore`).

### 2e. Billing alert (recommended)
AWS console → **Billing and Cost Management** → **Budgets** → **Create budget** → "Zero spend
budget" or a $1 monthly budget, with your email. You'll be emailed if anything ever costs money.

---

## 3. Run locally

```bash
cd "/Users/reuvikupchik/Python Projects/storybook"
source venv/bin/activate
pip install -r requirements.txt     # new packages: authlib, requests, boto3
python app.py                       # http://localhost:5001
```
Sign in with Google, make a book, sign out, sign back in, and check that it's still under **My books**.

**Free test mode:** add `FAKE_IMAGES=1` to `.env` and restart. Books are drawn with placeholder
images in a few seconds, with no OpenAI calls, so you can test sign-in, saving and the
progress bar without spending anything. A yellow bar at the top shows when it's on.
**Remove it (or set it to 0) on Render** so real users get real books.

---

## 4. Render

1. Service → **Environment**: add every variable from `.env`:
   `OPENAI_API_KEY`, `FLASK_SECRET_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
   `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `DYNAMODB_TABLE`, `S3_BUCKET`.
   (Not `FAKE_IMAGES`, and not `PORT`.)
2. Service → **Settings** → **Start command**:
   ```
   gunicorn app:app --workers 1 --threads 8 --timeout 120
   ```
   (Books are now drawn in the background, so requests are quick; the threads let the progress
   bar keep updating while a book is being drawn.)
3. Push your code; Render redeploys. Check **Logs** for a line like
   `storage=aws table=storybook bucket=...`. That confirms it's using AWS.

---

## 5. Logs

Every important event is one line in Render's **Logs** tab, for example:
```
INFO storybook.auth login user=1093...
INFO storybook.app book_created user=1093... book=3f2c...
INFO storybook.generator image_done user=1093... book=3f2c... image=character seconds=24.1
ERROR storybook.generator image_failed user=1093... book=3f2c... image=page2 seconds=31.0 error=...
INFO storybook.generator book_finished user=1093... book=3f2c... status=done seconds=58.7
INFO storybook.app pdf_download user=1093... book=3f2c... bytes=1432211
```
Other events: `login_failed`, `logout`, `rate_limited`, `retry_started`, `book_stalled`,
`book_deleted`, `server_error`. Users are identified by Google's numeric id, not their email.
