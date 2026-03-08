import urllib.request, json, time, sys
from app.database import SessionLocal
from app.models.submission import Submission

url = 'http://localhost:8000/api/code/submit'
data = json.dumps({
    'user_id': 'd3775024-8d1b-44dd-8fc1-3c55c39d3e55',
    'language': 'python',
    'problem_description': '',
    'code': 'print("hello")'
}).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json', 'accept': 'application/json'}, method='POST')

try:
    with urllib.request.urlopen(req) as response:
        resp = json.loads(response.read().decode('utf-8'))
        job_id = resp['job_id']
        print(f'Submitted: {job_id}')
except Exception as e:
    print('Failed to submit:', e)
    sys.exit(1)

time.sleep(5)

db = SessionLocal()
s = db.query(Submission).filter(Submission.id == job_id).first()
if s and s.feedback:
    errs = s.feedback.get('errors', [])
    if errs:
        print('WHY:', errs[0].get('why'))
else:
    print('Job not finished or no feedback')
