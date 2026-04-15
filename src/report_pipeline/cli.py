from argparse import ArgumentParser
from pathlib import Path

from report_pipeline.markdown_report import generate_markdown_report
from report_pipeline.pipeline import run_extract
from report_pipeline.pdf_export import export_pdf
from report_pipeline.render_inputs import build_render_context, load_render_bundle


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(prog="report-pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)
    extract = subparsers.add_parser("extract")
    extract.add_argument("--lab-xls")
    extract.add_argument("--standard-xlsx")
    extract.add_argument("--output-dir")
    extract.add_argument("--personal-info-xlsx", required=False, default=None)
    render = subparsers.add_parser("render")
    render.add_argument("--input-dir")
    render.add_argument("--markdown-output")
    render.add_argument("--pdf-output")
    subparsers.add_parser("assemble")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "extract":
        if not args.lab_xls or not args.standard_xlsx or not args.output_dir:
            parser.error("extract requires --lab-xls, --standard-xlsx, and --output-dir")
        run_extract(args.lab_xls, args.standard_xlsx, args.output_dir, args.personal_info_xlsx)
        return 0

    if args.command == "render":
        if not args.input_dir or not args.markdown_output or not args.pdf_output:
            parser.error("render requires --input-dir, --markdown-output, and --pdf-output")
        bundle = load_render_bundle(args.input_dir)
        context = build_render_context(bundle)
        markdown_path = Path(args.markdown_output)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)

        markdown = generate_markdown_report(context)
        markdown_path.write_text(markdown, encoding="utf-8")
        export_pdf(
            str(markdown_path),
            args.pdf_output,
            context["title"],
            context["hospital_name"],
            patient_name=context.get("patient_name", ""),
            report_date=context.get("report_date", ""),
            institution_name=context.get("institution_name", ""),
            cover_patient=f"{context.get('patient_name', '')}  {context.get('patient_gender', '')}  {context.get('patient_age', '')}岁",
        )
        return 0

    if args.command == "assemble":
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
