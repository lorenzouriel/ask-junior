"""Notifier package for Airflow DAGs"""
from .slack import slack_fail_alert

__all__ = ['slack_fail_alert']
