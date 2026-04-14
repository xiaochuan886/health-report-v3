from report_pipeline.cli import build_parser


def test_build_parser_exposes_subcommands():
    parser = build_parser()

    assert parser.parse_args(["extract"]).command == "extract"
    assert parser.parse_args(["render"]).command == "render"
    assert parser.parse_args(["assemble"]).command == "assemble"

    try:
        parser.parse_args([])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected parse_args([]) to fail")
