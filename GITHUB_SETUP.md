# GitHub Setup Guide 🚀

## Quick Steps to Push to GitHub

### Option 1: Using GitHub Desktop (Easiest)

1. **Open GitHub Desktop**
2. **File → Add Local Repository**
3. Browse to: `C:\Users\prati\Documents\AWS-ETL-redshit-pipeline`
4. Click **Add Repository**
5. Click **Publish repository**
6. Choose repository name: `AWS-ETL-redshift-pipeline`
7. Uncheck "Keep this code private" (if you want public)
8. Click **Publish repository**

✅ Done! Your project is now on GitHub.

---

### Option 2: Using Git Command Line

#### Step 1: Create Repository on GitHub

1. Go to https://github.com/new
2. Repository name: `AWS-ETL-redshift-pipeline`
3. Description: "Complete AWS data engineering pipeline with Glue, Redshift, and Power BI"
4. Choose Public or Private
5. **DO NOT** initialize with README, .gitignore, or license (we already have these)
6. Click **Create repository**

#### Step 2: Add Remote and Push

```bash
# Navigate to project directory
cd C:\Users\prati\Documents\AWS-ETL-redshit-pipeline

# Add GitHub remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/AWS-ETL-redshift-pipeline.git

# Verify remote was added
git remote -v

# Rename branch to main (GitHub's default)
git branch -M main

# Push to GitHub
git push -u origin main
```

#### Step 3: Verify on GitHub

Visit: `https://github.com/YOUR_USERNAME/AWS-ETL-redshift-pipeline`

You should see all your files!

---

### Option 3: Using VS Code / Cursor

1. **Open Source Control panel** (Ctrl+Shift+G)
2. Click **Publish to GitHub**
3. Choose **Publish to GitHub public repository**
4. Select repository name: `AWS-ETL-redshift-pipeline`
5. Select files to include (select all)
6. Click **OK**

✅ Done!

---

## Troubleshooting

### Error: Authentication Failed

**Solution 1: Use Personal Access Token (PAT)**

1. Go to GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token (classic)
3. Select scopes: `repo`, `workflow`
4. Copy the token
5. When pushing, use token as password:
   ```bash
   Username: YOUR_GITHUB_USERNAME
   Password: [paste your token]
   ```

**Solution 2: Use SSH**

```bash
# Generate SSH key
ssh-keygen -t ed25519 -C "your_email@example.com"

# Copy public key
cat ~/.ssh/id_ed25519.pub

# Add to GitHub: Settings → SSH and GPG keys → New SSH key

# Change remote to SSH
git remote set-url origin git@github.com:YOUR_USERNAME/AWS-ETL-redshift-pipeline.git

# Push
git push -u origin main
```

### Error: Repository Already Exists

```bash
# Remove existing remote
git remote remove origin

# Add correct remote
git remote add origin https://github.com/YOUR_USERNAME/AWS-ETL-redshift-pipeline.git

# Push
git push -u origin main
```

---

## After Pushing to GitHub

### 1. Enable GitHub Actions

GitHub Actions will automatically run on push. Check:
- Go to repository → **Actions** tab
- You should see CI/CD workflow running

### 2. Add Repository Secrets (for CI/CD)

Go to: **Settings → Secrets and variables → Actions → New repository secret**

Add these secrets:
```
AWS_ACCESS_KEY_ID: your-aws-access-key
AWS_SECRET_ACCESS_KEY: your-aws-secret-key
S3_BUCKET_SCRIPTS: your-curated-data-bucket
REDSHIFT_HOST: your-cluster.region.redshift.amazonaws.com
REDSHIFT_PASSWORD: your-redshift-password
SLACK_WEBHOOK: your-slack-webhook (optional)
```

### 3. Add Repository Topics

**Settings → General → Topics**

Add topics:
- `data-engineering`
- `aws`
- `etl`
- `redshift`
- `glue`
- `pyspark`
- `airflow`
- `power-bi`
- `data-pipeline`
- `star-schema`

### 4. Enable GitHub Pages (optional)

If you want to host documentation:
1. **Settings → Pages**
2. Source: **Deploy from a branch**
3. Branch: **main**, folder: **/ (root)**
4. Click **Save**

---

## Update README with Your GitHub Username

Before pushing, update these files with your actual GitHub username:

1. **README.md**
   - Line: `git clone https://github.com/YOUR_USERNAME/...`
   - Line: `Project Link: https://github.com/YOUR_USERNAME/...`
   - Line: `View results at: https://github.com/YOUR_USERNAME/...`

2. **README.md** - Contact section
   - Update email: `Your Name - your.email@example.com`

---

## Git Workflow for Future Changes

```bash
# Check status
git status

# Add changes
git add .

# Commit with message
git commit -m "Add new feature"

# Push to GitHub
git push

# Create a new branch
git checkout -b feature/new-feature

# Push new branch
git push -u origin feature/new-feature
```

---

## Repository Structure Verification

Your repository should have this structure:

```
AWS-ETL-redshift-pipeline/
├── .github/workflows/
│   └── ci.yml
├── dags/
│   └── etl_glue_redshift_dag.py
├── data_samples/
│   ├── customers.csv
│   ├── locations.csv
│   ├── products.csv
│   └── sales.csv
├── glue_jobs/
│   └── raw_to_curated.py
├── powerbi/
│   └── README.md
├── sql/
│   ├── create_redshift_schema.sql
│   └── load_redshift_tables.sql
├── tests/
│   └── pandera_tests.py
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
```

---

## Make Your Repository Stand Out

### 1. Add a Great Repository Description

```
Complete AWS data engineering pipeline: 
CSV → S3 → Glue ETL (PySpark) → Redshift (star schema) → Power BI. 
Includes Airflow orchestration, Pandera data quality tests, and CI/CD with GitHub Actions.
```

### 2. Add Repository Website

If you have a live demo or documentation site, add the URL in:
**Settings → General → Website**

### 3. Pin Repository (on your profile)

Go to your GitHub profile → **Customize your pins** → Select this repository

---

## Next Steps After GitHub Upload

1. ✅ Repository created and pushed
2. ⬜ Add GitHub Actions secrets for CI/CD
3. ⬜ Update README with your GitHub username
4. ⬜ Add repository topics and description
5. ⬜ Share on LinkedIn/Twitter
6. ⬜ Add to your resume/portfolio

---

**🎉 Congratulations! Your data engineering project is now on GitHub!**

Share it with recruiters and showcase your skills! 🚀

