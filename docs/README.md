# Apache Jira Scraper for LLM Training Data

This project scrapes Apache Jira issues and converts them into structured JSONL format suitable for LLM training. It implements a robust, fault-tolerant system with resume capability.

## Features

- Fetches issues, comments, and metadata from Apache Jira
- Handles pagination and rate limits gracefully
- Resumes from the last successful state if interrupted
- Converts raw Jira data into structured JSONL format
- Creates derived tasks for LLM training (summarization, classification, Q&A)
- Handles request failures, retries, and timeouts
- Manages HTTP 429 and 5xx responses
- Deals with empty or malformed data

## Architecture

The scraper follows a modular design with the following components:

1. **JiraClient** (`jira_client.py`) - Handles all interactions with the Apache Jira REST API
2. **DataTransformer** (`data_transformer.py`) - Converts raw Jira data into structured formats
3. **StateManager** (`state_manager.py`) - Manages scraping state for resume capability
4. **ScraperManager** (`scraper_manager.py`) - Orchestrates the entire scraping process
5. **ApacheJiraScraper** (`scraper.py`) - Main entry point

## Setup

1. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the scraper:
   ```bash
   python scraper.py
   ```

## Configuration

The scraper can be configured by modifying the `ApacheJiraScraper` instantiation in `scraper.py`:

```python
# Default configuration
scraper = ApacheJiraScraper(
    projects=["SPARK"],     # List of Jira projects to scrape
    output_dir="output"     # Directory to save JSONL files
)
```

## Output Format

The scraper generates JSONL files with the following structure:

```json
{
  "issue_key": "SPARK-1234",
  "metadata": {
    "title": "Issue title",
    "status": "Resolved",
    "priority": "Major",
    "project": "SPARK"
  },
  "content": {
    "description": "Issue description",
    "comments": ["Comment 1", "Comment 2"]
  },
  "derived_tasks": [
    {
      "task_type": "summarization",
      "input": "Title: Issue title\nDescription: Issue description",
      "target": "Summarize: Issue title"
    },
    {
      "task_type": "classification",
      "input": "Title: Issue title\nDescription: Issue description",
      "target": "Major"
    },
    {
      "task_type": "question_answering",
      "input": "Question: Issue title\nContext: Issue description",
      "target": "Comment 1"
    }
  ]
}
```

## Resume Capability

The scraper automatically saves its state to `state.json` after processing each batch of issues. If the process is interrupted, it will resume from the last saved position for each project.

## Error Handling

The scraper implements comprehensive error handling:

- **Rate Limiting**: Automatically waits when receiving HTTP 429 responses
- **Server Errors**: Retries requests when receiving HTTP 5xx responses
- **Network Issues**: Handles timeouts and connection failures gracefully
- **Data Issues**: Continues processing when encountering malformed data
- **Transform Errors**: Logs failed transformations to `failed.json`

## Optimization Strategies

1. **Efficient API Usage**: Implements proper rate limiting and batching
2. **Memory Management**: Processes issues in a streaming fashion to minimize memory usage
3. **Resume Capability**: Eliminates the need to reprocess already scraped data
4. **Error Recovery**: Continues processing after failures rather than stopping completely
5. **Logging**: Provides detailed logs for monitoring and debugging

## Future Improvements

1. **Parallel Processing**: Implement concurrent scraping of multiple projects
2. **Enhanced Retry Logic**: Add exponential backoff for failed requests
3. **Data Validation**: Add more comprehensive validation of Jira data
4. **Configuration File**: Support external configuration files
5. **Metrics Collection**: Add scraping metrics and performance monitoring
6. **Incremental Updates**: Support updating existing datasets with new issues