#!/usr/bin/env python3
"""
Clockodo Time Entry Scheduler

A Python script to automate time entry creation in Clockodo.
Converts the original bash script to a more robust Python implementation.
"""

import argparse
import json
import logging
import os
import random
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import requests
from dateutil import tz
from dateutil.parser import parse as parse_date


class TimeEntry:
    """Represents a single time entry for Clockodo."""
    
    def __init__(self, customer_id: int, service_id: int, billable: bool,
                 time_since: datetime, time_until: datetime):
        self.customer_id = customer_id
        self.service_id = service_id
        self.billable = billable
        self.time_since = time_since
        self.time_until = time_until
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for API payload."""
        return {
            "customers_id": self.customer_id,
            "services_id": self.service_id,
            "billable": 1 if self.billable else 0,
            "time_since": self.time_since.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "time_until": self.time_until.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
    
    def duration(self) -> timedelta:
        """Calculate duration of the time entry."""
        return self.time_until - self.time_since


class ClockodoAPI:
    """Handles Clockodo API interactions."""
    
    def __init__(self, api_user: str, api_key: str, external_app: str):
        self.api_user = api_user
        self.api_key = api_key
        self.external_app = external_app
        self.base_url = "https://my.clockodo.com/api/v2"
        self.session = requests.Session()
        self.session.headers.update({
            "X-ClockodoApiUser": self.api_user,
            "X-ClockodoApiKey": self.api_key,
            "X-Clockodo-External-Application": self.external_app,
            "Content-Type": "application/json"
        })
    
    def create_entry(self, entry: TimeEntry, dry_run: bool = False) -> bool:
        """Create a single time entry."""
        if dry_run:
            logging.info(f"DRY RUN: Would create entry {entry.time_since} - {entry.time_until}")
            return True
        
        try:
            response = self.session.post(
                f"{self.base_url}/entries",
                json=entry.to_dict(),
                timeout=30
            )
            response.raise_for_status()
            logging.info(f"Created entry: {entry.time_since} - {entry.time_until}")
            return True
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to create entry: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test API connection."""
        try:
            response = self.session.get(f"{self.base_url}/user", timeout=10)
            response.raise_for_status()
            logging.info("API connection successful")
            return True
        except requests.exceptions.RequestException as e:
            logging.error(f"API connection failed: {e}")
            return False


class WorkScheduler:
    """Generates work schedules with breaks."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.timezone = tz.gettz(config.get("timezone", "UTC"))
    
    def is_business_day(self, date: datetime) -> bool:
        """Check if date is a business day (not weekend or excluded)."""
        # Check weekend (Monday=0, Sunday=6)
        if date.weekday() >= 5:  # Saturday or Sunday
            return False
        
        # Check excluded dates
        date_str = date.strftime("%Y-%m-%d")
        excluded_dates = self.config.get("excluded_dates", [])
        if date_str in excluded_dates:
            return False
        
        return True
    
    def generate_work_blocks(self, date: datetime) -> List[TimeEntry]:
        """Generate work blocks for a given date."""
        if not self.is_business_day(date):
            return []
        
        # Get configuration
        customer_id = self.config["customer_id"]
        service_id = self.config["service_id"]
        billable = self.config.get("billable", True)
        
        # Generate random start time (11:00, 11:30, or 12:00 local time)
        start_options = self.config.get("start_time_options", ["11:00", "11:30", "12:00"])
        start_time_str = random.choice(start_options)
        start_hour, start_minute = map(int, start_time_str.split(":"))
        
        # Create start and end times in local timezone
        local_start = date.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
        local_start = local_start.replace(tzinfo=self.timezone)
        
        # Fixed end time
        end_time_str = self.config.get("end_time", "21:00")
        end_hour, end_minute = map(int, end_time_str.split(":"))
        local_end = date.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
        local_end = local_end.replace(tzinfo=self.timezone)
        
        # Convert to UTC
        utc_start = local_start.astimezone(tz.UTC)
        utc_end = local_end.astimezone(tz.UTC)
        
        # Calculate break time (30 minutes at midpoint)
        total_minutes = int((utc_end - utc_start).total_seconds() / 60)
        break_start_minutes = total_minutes // 2
        
        # Round break to nearest 30-minute interval
        remainder = break_start_minutes % 30
        if remainder < 15:
            break_start_minutes -= remainder
        else:
            break_start_minutes += (30 - remainder)
        
        break_start = utc_start + timedelta(minutes=break_start_minutes)
        break_end = break_start + timedelta(minutes=30)
        
        # Create two work blocks
        entries = []
        
        # First work block (start to break)
        if break_start > utc_start:
            entries.append(TimeEntry(
                customer_id=customer_id,
                service_id=service_id,
                billable=billable,
                time_since=utc_start,
                time_until=break_start
            ))
        
        # Second work block (break to end)
        if utc_end > break_end:
            entries.append(TimeEntry(
                customer_id=customer_id,
                service_id=service_id,
                billable=billable,
                time_since=break_end,
                time_until=utc_end
            ))
        
        return entries
    
    def generate_schedule(self, start_date: datetime, end_date: datetime) -> List[TimeEntry]:
        """Generate complete schedule for date range."""
        entries = []
        current_date = start_date
        
        while current_date <= end_date:
            daily_entries = self.generate_work_blocks(current_date)
            entries.extend(daily_entries)
            current_date += timedelta(days=1)
        
        return entries


def load_config(config_path: str) -> Dict:
    """Load configuration from JSON file."""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Configuration file not found: {config_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in configuration file: {e}")
        sys.exit(1)


def setup_logging(level: str = "INFO"):
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Clockodo Time Entry Scheduler")
    parser.add_argument("--config", default="config.json", help="Configuration file path")
    parser.add_argument("--dry-run", action="store_true", help="Preview mode without API calls")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="End date (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    
    # Load configuration
    config = load_config(args.config)
    
    # Override dates if provided via command line
    if args.start_date:
        config["start_date"] = args.start_date
    if args.end_date:
        config["end_date"] = args.end_date
    
    # Parse dates
    try:
        start_date = parse_date(config["start_date"]).date()
        end_date = parse_date(config["end_date"]).date()
    except Exception as e:
        logging.error(f"Invalid date format: {e}")
        sys.exit(1)
    
    # Get API credentials from environment variables
    api_user = os.getenv("CLOCKODO_API_USER")
    api_key = os.getenv("CLOCKODO_API_KEY")
    
    if not api_user or not api_key:
        logging.error("API credentials not found in environment variables")
        logging.error("Please set CLOCKODO_API_USER and CLOCKODO_API_KEY")
        sys.exit(1)
    
    # Initialize components
    external_app = config.get("external_app", "Python Scheduler")
    api = ClockodoAPI(api_user, api_key, external_app)
    scheduler = WorkScheduler(config)
    
    # Skip connection test - go directly to entries like bash script
    
    # Generate schedule
    logging.info(f"Generating schedule from {start_date} to {end_date}")
    entries = scheduler.generate_schedule(
        datetime.combine(start_date, datetime.min.time()),
        datetime.combine(end_date, datetime.min.time())
    )
    
    if not entries:
        logging.warning("No work entries generated")
        return
    
    # Create entries
    logging.info(f"Creating {len(entries)} time entries...")
    success_count = 0
    
    for entry in entries:
        if api.create_entry(entry, dry_run=args.dry_run):
            success_count += 1
        
        # Rate limiting
        if not args.dry_run:
            time.sleep(1)
    
    # Summary
    total_duration = sum([entry.duration() for entry in entries], timedelta())
    logging.info(f"Successfully created {success_count}/{len(entries)} entries")
    logging.info(f"Total work time: {total_duration}")


if __name__ == "__main__":
    main()