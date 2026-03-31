#!/usr/bin/env python3
"""Sales Hunter - AI-powered sales acquisition agent CLI."""

import os
import sys

import click
import yaml

from app.core.engine import SalesHunterEngine
from app.utils.logger import setup_logger

DEFAULT_CONFIG = "config.yaml"


def load_config(config_path: str) -> dict:
    try:
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        click.echo(f"Config file not found: {config_path}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Failed to load config: {e}", err=True)
        sys.exit(1)


@click.group()
def cli():
    """Sales Hunter - AI-powered sales acquisition agent."""
    pass


@cli.command()
@click.option("--dry-run", is_flag=True, help="Run without making any changes")
@click.option(
    "--input",
    "input_path",
    default="data/input/sample_prospects.csv",
    show_default=True,
    help="Path to prospect CSV file",
)
@click.option(
    "--config",
    "config_path",
    default=DEFAULT_CONFIG,
    show_default=True,
    help="Path to config YAML file",
)
def ingest(dry_run: bool, input_path: str, config_path: str):
    """Load and enrich prospects from CSV file."""
    config = load_config(config_path)
    engine = SalesHunterEngine(config, dry_run=dry_run)
    count = engine.ingest(input_path)
    click.echo(f"Ingested {count} prospects.")


@cli.command()
@click.option("--dry-run", is_flag=True, help="Run without making any changes")
@click.option(
    "--config",
    "config_path",
    default=DEFAULT_CONFIG,
    show_default=True,
    help="Path to config YAML file",
)
def score(dry_run: bool, config_path: str):
    """Score and prioritize prospects."""
    config = load_config(config_path)
    engine = SalesHunterEngine(config, dry_run=dry_run)
    count = engine.score()
    click.echo(f"Scored {count} prospects.")


@cli.command("send-first")
@click.option("--dry-run", is_flag=True, help="Simulate sending without actually sending emails")
@click.option("--limit", default=None, type=int, help="Max emails to send")
@click.option(
    "--draft",
    is_flag=True,
    help="Generate messages and save to CRM but do not send",
)
@click.option(
    "--config",
    "config_path",
    default=DEFAULT_CONFIG,
    show_default=True,
    help="Path to config YAML file",
)
def send_first(dry_run: bool, limit: int, draft: bool, config_path: str):
    """Generate and send first outreach emails."""
    config = load_config(config_path)
    engine = SalesHunterEngine(config, dry_run=dry_run)
    count = engine.send_first(limit=limit, draft=draft)
    if draft:
        click.echo(f"Generated {count} draft messages (not sent).")
    else:
        click.echo(f"Sent {count} emails.")


@cli.command("fetch-replies")
@click.option("--dry-run", is_flag=True, help="Run without making any changes")
@click.option(
    "--config",
    "config_path",
    default=DEFAULT_CONFIG,
    show_default=True,
    help="Path to config YAML file",
)
def fetch_replies(dry_run: bool, config_path: str):
    """Fetch and record email replies from Gmail."""
    config = load_config(config_path)
    engine = SalesHunterEngine(config, dry_run=dry_run)
    count = engine.fetch_replies()
    click.echo(f"Found {count} new replies.")


@cli.command("process-replies")
@click.option("--dry-run", is_flag=True, help="Run without making any changes")
@click.option(
    "--config",
    "config_path",
    default=DEFAULT_CONFIG,
    show_default=True,
    help="Path to config YAML file",
)
def process_replies(dry_run: bool, config_path: str):
    """Classify replies and generate followup messages."""
    config = load_config(config_path)
    engine = SalesHunterEngine(config, dry_run=dry_run)
    count = engine.process_replies()
    click.echo(f"Processed {count} replies.")


@cli.command("generate-report")
@click.option(
    "--config",
    "config_path",
    default=DEFAULT_CONFIG,
    show_default=True,
    help="Path to config YAML file",
)
def generate_report(config_path: str):
    """Generate activity and performance report."""
    config = load_config(config_path)
    engine = SalesHunterEngine(config)
    report = engine.generate_report()
    click.echo(f"Report generated with {report['total']} prospects.")


if __name__ == "__main__":
    cli()
