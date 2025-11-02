#!/usr/bin/env python3
"""
Apache Jira Scraper - Under 200 lines
Scrapes Apache Jira issues and converts to JSONL for LLM training.
"""

import requests, time, json, os, re, logging
from urllib.parse import urlencode
from typing import Dict, List, Optional, Iterator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

class ApacheJiraScraper:
    def __init__(self, projects: Optional[List[str]] = None, output_dir: str = "output"):
        self.projects, self.output_dir = projects or ["SPARK"], output_dir
        self.base_url = "https://issues.apache.org/jira"
        self.session = requests.Session()
        self.session.headers.update({'Accept': 'application/json'})
        os.makedirs(self.output_dir, exist_ok=True)
    
    def _load_state(self) -> Dict:
        """Load last scraped index for each project."""
        if os.path.exists("state.json"):
            try:
                with open("state.json", 'r') as f:
                    return json.load(f)
            except: pass
        return {p: 0 for p in self.projects}
    
    def _save_state(self, state: Dict): 
        """Save current scraping state."""
        try:
            with open("state.json", 'w') as f:
                json.dump(state, f)
        except: pass
    
    def _log_failed_issue(self, issue_key: str, error: str):
        """Log failed issues for retry."""
        try:
            failed = []
            if os.path.exists("failed.json"):
                with open("failed.json", 'r') as f:
                    failed = json.load(f)
            failed.append({"issue": issue_key, "error": error})
            with open("failed.json", 'w') as f:
                json.dump(failed, f)
        except: pass
    
    def _request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make API request with error handling."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        if params: url = f"{url}?{urlencode(params)}"
        
        try:
            resp = self.session.get(url, timeout=30)
            if resp.status_code == 429:
                wait = int(resp.headers.get('Retry-After', 5))
                logger.warning(f"Rate limited, waiting {wait}s")
                time.sleep(wait)
                return self._request(endpoint, params)
            elif resp.status_code >= 500:
                time.sleep(1)
                resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return None
    
    def _fetch_issues(self, project: str, start: int, max_results: int = 50) -> Optional[Dict]:
        """Fetch issues with pagination."""
        params = {
            'jql': f"project = {project}",
            'startAt': start,
            'maxResults': max_results,
            'fields': 'summary,description,status,priority,assignee,reporter,created,updated,labels,comment'
        }
        return self._request("/rest/api/2/search", params)
    
    def _get_all_issues(self, project: str) -> Iterator[Dict]:
        """Generator for all project issues with resume capability."""
        state = self._load_state()
        start_at = state.get(project, 0)
        page_size = 50
        
        logger.info(f"Starting {project} from index {start_at}")
        
        while True:
            data = self._fetch_issues(project, start_at, page_size)
            if not data: break
            
            issues = data.get('issues', [])
            if not issues: break
            
            for issue in issues:
                yield issue
            
            # Update state
            start_at += len(issues)
            state[project] = start_at
            self._save_state(state)
            
            total = data.get('total', 0)
            logger.info(f"{project}: {start_at}/{total} issues")
            
            if start_at >= total: break
            time.sleep(0.1)
    
    def _clean(self, text: str) -> str:
        """Clean text content."""
        if not text: return ""
        return re.sub(r'\s+', ' ', text).strip()
    
    def _extract_comments(self, fields: Dict) -> List[str]:
        """Extract and clean comments."""
        comments = []
        data = fields.get('comment', {}).get('comments', [])
        for c in data:
            body = c.get('body', '')
            if body: comments.append(self._clean(body))
        return comments
    
    def _transform(self, issue: Dict) -> Dict:
        """Transform issue to structured format."""
        key = issue.get('key', '')
        fields = issue.get('fields', {})
        
        title = self._clean(fields.get('summary', ''))
        desc = self._clean(fields.get('description', ''))
        status = fields.get('status', {}).get('name', '')
        priority = fields.get('priority', {}).get('name', '')
        comments = self._extract_comments(fields)
        
        # Create training tasks
        tasks = []
        if title and desc:
            tasks.append({
                "task_type": "summarization",
                "input": f"Title: {title}\nDescription: {desc}",
                "target": f"Summarize: {title}"
            })
            if priority:
                tasks.append({
                    "task_type": "classification",
                    "input": f"Title: {title}\nDescription: {desc}",
                    "target": priority
                })
        if title and desc and comments:
            tasks.append({
                "task_type": "question_answering",
                "input": f"Question: {title}\nContext: {desc}",
                "target": comments[0]
            })
        
        return {
            "issue_key": key,
            "metadata": {
                "title": title,
                "status": status,
                "priority": priority,
                "project": key.split('-')[0] if '-' in key else ''
            },
            "content": {"description": desc, "comments": comments},
            "derived_tasks": tasks
        }
    
    def run(self):
        """Main scraping and transformation pipeline."""
        logger.info(f"Projects: {', '.join(self.projects)}")
        total = 0
        
        for project in self.projects:
            logger.info(f"Scraping {project}")
            issues = list(self._get_all_issues(project))
            logger.info(f"Found {len(issues)} issues in {project}")
            
            if issues:
                # Save to JSONL
                path = os.path.join(self.output_dir, f"{project.lower()}_issues.jsonl")
                logger.info(f"Saving to {path}")
                
                count = 0
                with open(path, 'w', encoding='utf-8') as f:
                    for issue in issues:
                        try:
                            data = self._transform(issue)
                            f.write(json.dumps(data, ensure_ascii=False) + '\n')
                            count += 1
                        except Exception as e:
                            key = issue.get('key', 'Unknown')
                            logger.error(f"Transform error for {key}: {e}")
                            self._log_failed_issue(key, str(e))
                
                logger.info(f"Saved {count} issues")
                total += count
        
        logger.info(f"Completed! Total: {total} issues")

def main():
    try:
        ApacheJiraScraper().run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    main()