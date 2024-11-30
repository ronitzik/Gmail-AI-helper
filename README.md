# Gmail AI Helper

Gmail AI Helper is a Python-based application that fetches emails from a Gmail account, processes them using a local LLM (Llama-3.2-3B-Instruct-Q4_0), and generates insightful visualizations based on categorized emails.

## Features

- Fetch emails from Gmail using the Gmail API.
- Categorize emails into **Work**, **School**, **Shopping**, and **Personal** using an LLM.
- Rank email priorities as **Urgent**, **Important**, or **Normal**.
- Determine if a response is required for each email.
- Visualize email data using matplotlib:
  - Pie chart: Distribution of email categories.
  - Stacked bar chart: Response requirements by category.
  - Bar chart: Priority distribution across categories.


## Installation

1. Clone the repository:
   - git clone https://github.com/your-username/Gmail-AI-helper.git
2. Create and activate a virtual environment:
   - python -m venv .venv
3. Add your Google API credentials.json file to the root directory.
4. Run the Redis server.

## Usage

1. Fetch emails and generate charts:
    - python src/gmail_fetch.py
2. The application will:
    - Fetch emails as defined in the max_results var.
    - Process them with the LLM.
    - Generate charts that display the distribution of email categories, priorities, and response requirements.
   

