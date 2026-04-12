from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from pathlib import Path

from dotenv import load_dotenv

from seo_agent import run_seo_recommendation

# CrewAI/Pydantic can emit this non-fatal serialization warning; keep CLI output clean.
warnings.filterwarnings(
    "ignore",
    message=r".*method callbacks cannot be serialized and will prevent checkpointing.*",
    category=UserWarning,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the CrewAI SEO agent for keyword recommendations."
    )
    parser.add_argument("--business-name", default="Acme Growth Labs")
    parser.add_argument("--website-url", default="https://example.com")
    parser.add_argument(
        "--core-offer",
        default="Marketing AI assistant for campaign planning and execution",
    )
    parser.add_argument("--industry", default="B2B SaaS")
    parser.add_argument(
        "--audience",
        default="startup founders, growth marketers, and lean marketing teams",
    )
    parser.add_argument("--target-market", default="English / US + Europe")
    parser.add_argument(
        "--conversion-goal",
        default="book product demo or start free trial",
    )
    parser.add_argument("--brand-voice", default="practical, expert, friendly")
    parser.add_argument(
        "--competitors",
        default="HubSpot AI, Jasper, Copy.ai, Notion AI",
    )
    parser.add_argument(
        "--output",
        default="seo_recommendations.json",
        help="Output JSON file path.",
    )
    parser.add_argument("--keyword-count", type=int, default=12)
    parser.add_argument("--cluster-count", type=int, default=4)
    parser.add_argument("--article-title-count", type=int, default=6)
    parser.add_argument("--landing-page-target-count", type=int, default=3)
    parser.add_argument("--next-actions-count", type=int, default=5)
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=900,
        help="Cap LLM output tokens to reduce rate-limit pressure.",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    os.environ["SEO_MAX_TOKENS"] = str(args.max_output_tokens)

    inputs = {
        "business_name": args.business_name,
        "website_url": args.website_url,
        "core_offer": args.core_offer,
        "industry": args.industry,
        "audience": args.audience,
        "target_market": args.target_market,
        "conversion_goal": args.conversion_goal,
        "brand_voice": args.brand_voice,
        "competitors": args.competitors,
        "keyword_count": args.keyword_count,
        "cluster_count": args.cluster_count,
        "article_title_count": args.article_title_count,
        "landing_page_target_count": args.landing_page_target_count,
        "next_actions_count": args.next_actions_count,
    }

    try:
        result = run_seo_recommendation(inputs)
    except RuntimeError as exc:
        print(f"Configuration error: {exc}")
        print(
            "Example .env for Hugging Face:\n"
            "HUGGINGFACE_API_KEY=your_key\n"
            "CREWAI_MODEL=Qwen/Qwen2.5-7B-Instruct"
        )
        sys.exit(1)
    except Exception as exc:
        print(f"Runtime error: {exc}")
        sys.exit(1)

    output_path = Path(args.output)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"SEO recommendations saved to: {output_path.resolve()}")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()





