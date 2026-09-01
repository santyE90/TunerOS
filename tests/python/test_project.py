from tuneros import PROJECT_NAME


def test_project_name_identifies_package() -> None:
    assert PROJECT_NAME == "TunerOS"
