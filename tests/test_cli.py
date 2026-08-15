from apartment_search.cli import main


def test_score_command_prints_summary(capsys):
    main(
        [
            "score",
            (
                "Montefiore room with roommates, renovated, 3800 ILS, "
                "September 2026, Mamad"
            ),
        ]
    )

    captured = capsys.readouterr()
    assert "SEND score" in captured.out
