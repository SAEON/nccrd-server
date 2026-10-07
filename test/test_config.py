"""Settings come from environment variables or a .env file (as in CI and local development)."""
import os

from nccrd.config import NCCRDDBConfig, NCCRDInnerConfig


def test_every_settings_group_reads_the_env_file(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "NCCRD_DB_HOST=db.example\nNCCRD_DB_NAME=nccrd\nNCCRD_DB_USER=user\nNCCRD_DB_PASS=secret\n"
        "NCCRD_JWT_SECRET=jwt\nNCCRD_SOMETHING_ELSE=ignored\n")
    monkeypatch.chdir(tmp_path)
    for name in [k for k in os.environ if k.startswith("NCCRD_")]:
        monkeypatch.delenv(name)
    assert NCCRDDBConfig().URL == "postgresql://user:secret@db.example:5432/nccrd"
    assert NCCRDInnerConfig().JWT_SECRET == "jwt"


def test_environment_variables_win_over_the_env_file(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("NCCRD_DB_HOST=from-file\nNCCRD_DB_NAME=n\nNCCRD_DB_USER=u\nNCCRD_DB_PASS=p\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NCCRD_DB_HOST", "from-env")
    assert NCCRDDBConfig().HOST == "from-env"
