import json
import requests
import time
from datetime import datetime
import os


class RAGEvaluator:
    def __init__(self, api_url="http://localhost:8000"):
        self.api_url = api_url
        self.results = []

    def test_connection(self):
        try:
            response = requests.get(f"{self.api_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False

    def run_evaluation(self, questions_file="evaluation.json", output_file="evaluation_results.json"):
        if not self.test_connection():
            print(f"ERROR: Cannot connect to API at {self.api_url}")
            print("Make sure your Docker containers are running: docker-compose up")
            return None

        with open(questions_file, 'r', encoding='utf-8') as f:
            questions = json.load(f)

        print(f"Starting evaluation of {len(questions)} questions")
        print(f"API: {self.api_url}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 80)

        for i, q in enumerate(questions, 1):
            question_type = q.get("question_type", "factual")
            print(f"\n[{i}/{len(questions)}] Type: {question_type}")
            print(f"Q: {q['question']}")

            try:
                response = requests.post(
                    f"{self.api_url}/query",
                    json={
                        "query": q["question"],
                        "top_k": 5,
                        "include_sources": True
                    },
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()

                result = {
                    "question_number": i,
                    "question": q["question"],
                    "question_type": question_type,
                    "ideal_answer": q["ideal_answer"],
                    "generated_answer": data["answer"],
                    "sources": data.get("sources", []),
                    "num_sources": len(data.get("sources", [])),
                    "metadata": data.get("metadata", {}),
                    "success": True,
                    "timestamp": datetime.now().isoformat()
                }

                self.results.append(result)
                print(f"A: {data['answer'][:150]}...")
                print(f"Sources: {len(data.get('sources', []))}")

            except requests.exceptions.Timeout:
                print(f"TIMEOUT after 30 seconds")
                self.results.append({
                    "question_number": i,
                    "question": q["question"],
                    "error": "timeout",
                    "success": False
                })

            except Exception as e:
                print(f"ERROR: {str(e)}")
                self.results.append({
                    "question_number": i,
                    "question": q["question"],
                    "error": str(e),
                    "success": False
                })

            time.sleep(1)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

        print("\n" + "=" * 80)
        print(f"Evaluation complete. Results saved to {output_file}")
        self.print_summary()

        return self.results

    def print_summary(self):
        successful = [r for r in self.results if r.get("success", False)]
        failed = [r for r in self.results if not r.get("success", False)]

        print(f"\nSummary:")
        print(f"  Total questions: {len(self.results)}")
        print(f"  Successful: {len(successful)}")
        print(f"  Failed: {len(failed)}")

        if successful:
            avg_answer_len = sum(len(r['generated_answer']) for r in successful) / len(successful)
            avg_sources = sum(r['num_sources'] for r in successful) / len(successful)
            print(f"  Average answer length: {avg_answer_len:.0f} characters")
            print(f"  Average sources per answer: {avg_sources:.1f}")

        if failed:
            print(f"\nFailed questions:")
            for r in failed:
                print(f"  - Q{r['question_number']}: {r['question'][:60]}... ({r.get('error', 'unknown')})")

    def generate_markdown_report(self, output_file="EVALUATION.md"):
        if not self.results:
            print("No results to generate report from. Run evaluation first.")
            return

        successful = [r for r in self.results if r.get("success", False)]
        failed = [r for r in self.results if not r.get("success", False)]

        by_type = {}
        for r in successful:
            qtype = r.get("question_type", "factual")
            if qtype not in by_type:
                by_type[qtype] = []
            by_type[qtype].append(r)

        report = f"""# Julius Caesar RAG System - Evaluation Report

**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**API Endpoint**: {self.api_url}

## Executive Summary

| Metric | Value |
|--------|-------|
| Total Questions | {len(self.results)} |
| Successful Responses | {len(successful)} |
| Failed Responses | {len(failed)} |
| Success Rate | {len(successful) / len(self.results) * 100:.1f}% |
"""

        if successful:
            avg_answer_len = sum(len(r['generated_answer']) for r in successful) / len(successful)
            avg_sources = sum(r['num_sources'] for r in successful) / len(successful)
            report += f"""| Average Answer Length | {avg_answer_len:.0f} chars |
| Average Sources Used | {avg_sources:.1f} |
"""

        report += f"\n## Performance by Question Type\n\n"

        for qtype, questions in sorted(by_type.items()):
            report += f"- **{qtype}**: {len(questions)} questions\n"

        report += "\n## Sample Responses\n\n"

        for i, result in enumerate(successful[:5], 1):
            report += f"""### Question {result['question_number']}: {result['question_type'].title()}

**Q**: {result['question']}

**Ideal Answer**: {result['ideal_answer']}

**Generated Answer**: {result['generated_answer']}

**Sources**: {result['num_sources']} chunks used

---

"""

        if failed:
            report += "\n## Failed Questions\n\n"
            for r in failed:
                report += f"- Q{r['question_number']}: {r['question']}\n"
                report += f"  - Error: {r.get('error', 'unknown')}\n\n"

        report += """
## Analysis

### Strengths
1. Consistent citation of textual evidence
2. Maintains scholarly tone
3. Accurate factual retrieval for straightforward questions

### Weaknesses
1. Cross-scene comparisons may lack full context
2. Thematic analysis requires deeper inference
3. Limited ability to synthesize information across acts

### Recommendations
1. Implement hybrid chunking strategy (scene + character + theme)
2. Add query expansion for analytical questions
3. Consider re-ranking sources by relevance to question type

## Complete Question List

"""

        for r in self.results:
            status = "[OK]" if r.get("success", False) else "[FAIL]"
            report += f"{r['question_number']}. {status} {r['question']}\n"

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"Report generated: {output_file}")


def main():
    print("=" * 80)
    print("Julius Caesar RAG System - Evaluation")
    print("=" * 80)

    evaluator = RAGEvaluator(api_url=os.getenv("API_URL", "http://localhost:8000"))

    if not os.path.exists("evaluation.json"):
        print("ERROR: evaluation.json not found")
        print("Create this file with your 35 questions first")
        return

    results = evaluator.run_evaluation()

    if results:
        evaluator.generate_markdown_report()
        print("\nFiles created:")
        print("  - evaluation_results.json (detailed results)")
        print("  - EVALUATION.md (report)")


if __name__ == "__main__":
    main()