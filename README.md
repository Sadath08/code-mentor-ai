# Code Mentor AI

An AI-powered code mentoring platform with personalized learning paths, code review, and gamification.

## Project Structure

```
code mentor-ai/
├── frontend/          # React + Vite frontend application
├── backend/           # FastAPI backend application
└── README.md
```

## Setup Instructions

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   copy .env.example .env
   ```
   Then edit `.env` and add your API keys:
   - OPENAI_API_KEY
   - GROQ_API_KEY
   - GEMINI_API_KEY
   - DATABASE_URL
   - SECRET_KEY

5. Run the backend:
   ```bash
   uvicorn app.main:app --reload
   ```

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Set up environment variables:
   ```bash
   copy .env.example .env
   ```
   Update `VITE_API_URL` if needed.

4. Run the development server:
   ```bash
   npm run dev
   ```

## Deployment to AWS

### Backend Deployment Options

1. **AWS Elastic Beanstalk** (Recommended for FastAPI)
2. **AWS Lambda + API Gateway** (Serverless)
3. **AWS ECS/Fargate** (Containerized)

### Frontend Deployment Options

1. **AWS Amplify** (Recommended - easiest)
2. **AWS S3 + CloudFront** (Static hosting)

### Pre-Deployment Checklist

- [ ] All `.env` files are in `.gitignore`
- [ ] `.env.example` files are committed (without real keys)
- [ ] Update `VITE_API_URL` in frontend `.env` to production backend URL
- [ ] Update `DATABASE_URL` to production database
- [ ] Change `SECRET_KEY` to a strong random value
- [ ] Set up AWS RDS for PostgreSQL database
- [ ] Configure CORS in backend for production frontend URL

## Environment Variables

### Backend (.env)
- API keys for OpenAI, Groq, and Gemini
- Database connection string
- Secret key for JWT tokens

### Frontend (.env)
- Backend API URL

**IMPORTANT**: Never commit `.env` files! Only commit `.env.example` templates.

## Git Workflow

```bash
# Add all changes except ignored files
git add .

# Commit changes
git commit -m "Your commit message"

# Push to repository
git push origin main
```

The `.gitignore` files will automatically exclude:
- API keys and secrets (.env files)
- Dependencies (node_modules, .venv)
- Build artifacts (dist, __pycache__)
- Database files
- Logs and temporary files

## Security Notes

1. **Never commit API keys** - They are in `.gitignore`
2. **Use environment variables** - For all sensitive data
3. **Rotate keys regularly** - Especially after team changes
4. **Use AWS Secrets Manager** - For production secrets
5. **Enable HTTPS** - For all production deployments
