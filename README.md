# 📊 Social Media Analyst

A Python-based social media analytics tool that ingests post data, identifies trends, and generates actionable growth insights to help companies grow.

---

## ✨ Features

| Capability | Details |
|---|---|
| **Data ingestion** | CSV and JSON (array or NDJSON); auto-detects delimiter; validates schema |
| **Trend analysis** | Top hashtags & keywords, engagement rate, CTR, follower growth, rising/declining detection |
| **Growth insights** | Best posting time/day, rising hashtags to leverage, platform focus, CTR tips |
| **Reporting** | JSON, CSV, and Markdown reports with ranked trend tables and KPI summaries |
| **CLI** | `python -m social_analyzer` with `analyze` and `validate` sub-commands |
| **Config file** | YAML or JSON config; all parameters overridable via CLI flags |

---

## 🗂️ Project Structure

```
social_analyzer/        # Main package
  __init__.py
  __main__.py           # `python -m social_analyzer` entry point
  ingestion.py          # CSV / JSON data loading & schema validation
  analysis.py           # Trend detection, engagement metrics, insights
  reporting.py          # JSON / CSV / Markdown report renderers
  cli.py                # argparse CLI (analyze, validate)
  utils.py              # Shared helpers (hashtag extraction, safe_divide, …)

config/
  default_config.yaml   # Default analysis parameters

data/
  posts.csv             # Sample dataset (498 posts, 4 platforms, 90 days)
  posts_sample.json     # Smaller JSON sample (30 posts)

tests/
  test_utils.py
  test_ingestion.py
  test_analysis.py
  test_reporting.py

pyproject.toml
requirements.txt
```

---

## 🚀 Quick Start

### 1. Install

```bash
# Clone the repo
git clone https://github.com/yash-singhh/yash-singhh.git
cd yash-singhh

# Create a virtual environment (optional but recommended)
python -m venv .venv && source .venv/bin/activate

# Install the package
pip install -e .
# PyYAML is needed for YAML config files:
pip install pyyaml
```

### 2. Run your first analysis

```bash
# Analyse the sample CSV — print Markdown to stdout
python -m social_analyzer analyze --input data/posts.csv --window 0

# Save a Markdown report
python -m social_analyzer analyze --input data/posts.csv --window 30 \
    --output reports/summary.md

# Save a JSON report
python -m social_analyzer analyze --input data/posts.csv --window 30 \
    --output reports/summary.json

# Save a CSV report
python -m social_analyzer analyze --input data/posts.csv --window 30 \
    --output reports/summary.csv

# Use a config file + override window via flag
python -m social_analyzer analyze --input data/posts.csv \
    --config config/default_config.yaml --window 7

# Validate data without running analysis
python -m social_analyzer validate --input data/posts.csv
```

---

## ⚙️ CLI Reference

```
python -m social_analyzer [--version] COMMAND [options]

Commands:
  analyze   Run trend analysis and generate a report.
  validate  Validate an input file's schema without running analysis.

analyze options:
  --input  / -i  PATH    Input CSV or JSON file (required)
  --output / -o  PATH    Output file (stdout if omitted)
  --format / -f  FMT     json | csv | markdown | md  (inferred from extension)
  --window / -w  DAYS    Look-back window in days (0 = all data)
  --top-n        N       Number of top trends to include
  --config / -c  PATH    YAML or JSON config file
  --verbose / -v         Enable debug logging

validate options:
  --input  / -i  PATH    Input CSV or JSON file (required)
```

---

## 📄 Data Format

### CSV

```csv
post_id,platform,timestamp,text,likes,comments,shares,impressions,clicks,followers
POST_00001,twitter,2024-03-01 10:00:00,"Excited to share our #AI work! #MachineLearning",150,20,8,3200,64,12000
POST_00002,instagram,2024-03-02 17:30:00,"5 tips to improve your #ContentMarketing strategy",200,35,15,5000,90,18000
```

**Required columns:** `post_id`, `platform`, `timestamp`, `text`

**Optional columns (default to 0):** `likes`, `comments`, `shares`, `impressions`, `clicks`, `followers`

### JSON

```json
[
  {
    "post_id": "J0001",
    "platform": "linkedin",
    "timestamp": "2024-03-01T10:00:00",
    "text": "Excited about #AI and #DataScience trends!",
    "likes": 120,
    "comments": 15,
    "shares": 6,
    "impressions": 2500,
    "clicks": 50,
    "followers": 8000
  }
]
```

Newline-delimited JSON (NDJSON) is also supported.

---

## ⚙️ Configuration File

```yaml
# config/default_config.yaml
window_days: 30           # Rolling look-back window (0 = all data)
top_n: 10                 # Number of top trends to display
rising_threshold: 1.2     # 20% uplift to be classed as "rising"
min_post_count: 2         # Min posts for a term to appear in trends
engagement_weight_likes: 1.0
engagement_weight_comments: 2.0
engagement_weight_shares: 3.0
```

---

## 📐 Metrics Explained

| Metric | Formula |
|---|---|
| **Engagement Rate (ER)** | `(likes + comments + shares) / impressions × 100` (falls back to `/followers` when impressions = 0) |
| **CTR** | `clicks / impressions × 100` |
| **Engagement Score** | `likes×w₁ + comments×w₂ + shares×w₃` (configurable weights) |
| **Rising / Declining** | Ratio of mean engagement in the recent half-window vs older half-window |

---

## 🧪 Running Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

86 unit tests covering utilities, ingestion, analysis, and reporting.

---

## 📑 Sample Report Output (Markdown)

```markdown
# Social Media Analytics Report

## Overview
| Parameter | Value |
|---|---|
| Total posts analysed | 498 |

## Platform KPIs
| Platform | Posts | Avg ER % | Avg CTR % |
|---|---|---|---|
| Linkedin | 118 | 5.70 | 2.21 |
| Twitter | 117 | 5.45 | 2.27 |

## Top Hashtags
| # | Hashtag | Posts | Direction |
|---|---|---|---|
| 1 | #startuplife | 160 | ➡️ stable |
| 2 | #machinelearning | 161 | 📈 rising |

## Growth Insights & Recommendations
1. [Posting Time] Post at 08:00 UTC to maximise engagement (avg ER: 5.94%).
2. [Platform Focus] Focus on LinkedIn, which yields the highest avg engagement rate.
```


Neural Network Status: [====================] 100% Complete
CUDA Toolkit: 13.0 | Driver: 555.0.0 | TensorRT: 10.0

     ██╗   ██╗ █████╗ ███████╗██╗  ██╗     
     ██║   ██║██╔══██╗██╔════╝██║  ██║     
     ██║   ██║███████║███████╗███████║     
     ╚██╗ ██╔╝██╔══██║╚════██║██╔══██║     
      ╚████╔╝ ██║  ██║███████║██║  ██║     
       ╚═══╝  ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝      



[CRITICAL] Coffee reserves at 12% — initiating emergency protocols...
[WARNING] Model exhibiting signs of philosophical awareness
[INFO] Training loss: 0.0042 | Accuracy: 99.9% | Focus: Highly Tuned
[DEBUG] Reason for success: Still unknown. Possibly dark magic.
[ERROR] Code ran perfectly on the first try. Please investigate.
[SYSTEM] Scheduling 2AM thought spirals & AI musings...

Current Mission:
└─ Teaching models *why* they exist  
   └─ Model response: "To minimize loss... and maximize meaning?"
      └─ Scheduling debate with Descartes.



class NeuralArchitect:

 def __init__(self):
 
        self.name = "Yash Singh"
        
        self.location = "Mumbai, India 🇮🇳"
        
        self.role = "AI Engineer @ Creative Finserve"
        self.interests = {
            "technical": ["Computer Vision", "Neural Architecture", "MLOps"],
            "research": ["Efficient Training", "Model Compression", "Few-Shot Learning"],
            "current_debug_status": "Trying to understand why my model predicts cats as pickles"
        }
    
    def handle_errors(self, error):
        if isinstance(error, CoffeeNotFoundError):
            self.brew_coffee()
        elif isinstance(error, ModelNotConvergingError):
            self.add_more_layers()  # Because that always helps, right?
        else:
            return "Have you tried turning it off and on again?"

    async def daily_routine(self):
        await self.train_models()
        await self.debug_life()
        await self.contemplate_existence_of_local_minima()

def initiate_neural_connection():
    """
    ⚠️ Warning: May involve discussions about:
    - 🤖 Why transformers are just spicy matrix multiplication
    - 🧠 The philosophical implications of gradient descent
    - 🪞 Whether consciousness is just a well-trained model
    """
    return "Let's collaborate on something extraordinary!"  

<!--
**yash-singhh/yash-singhh** is a ✨ _special_ ✨ repository because its `README.md` (this file) appears on your GitHub profile.

Here are some ideas to get you started:

- 🔭 I’m currently working on ...
- 🌱 I’m currently learning ...
- 👯 I’m looking to collaborate on ...
- 🤔 I’m looking for help with ...
- 💬 Ask me about ...
- 📫 How to reach me: ...
- 😄 Pronouns: ...
- ⚡ Fun fact: ...
-->
