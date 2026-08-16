from datetime import datetime
from typing import List, Optional
import logging
from dataclasses import dataclass
import pandas as pd


@dataclass
class Update:
    """Represents a single update entry with date and content."""
    date: datetime
    content: str

    def __str__(self) -> str:
        """String representation of the update."""
        return f"{self.date.strftime('%Y-%m-%d')}: {self.content}"

    def __repr__(self) -> str:
        """Official string representation of the update."""
        return f"Update(date={self.date!r}, content={self.content!r})"


class UpdateReader:
    """
    Reads and manages a collection of updates from a public Google Spreadsheet.
    
    This class uses pandas to read updates directly from the Google Sheets CSV export.
    """
    
    def __init__(self, spreadsheet_id: str, sheet_gid: Optional[str] = None):
        """
        Initialize the UpdateReader with a Google Spreadsheet ID.
        
        Args:
            spreadsheet_id: The ID of the Google Spreadsheet containing updates
            sheet_gid: Optional specific sheet GID number (found in sheet URL)
        """
        self.spreadsheet_id = spreadsheet_id
        self.sheet_gid = sheet_gid
        self.updates: List[Update] = []
        self.metadata = {
            "title": "Recent Updates",
            "description": "Recent updates and news about the project",
            "link_text": "View all updates"
        }
        self.logger = logging.getLogger(__name__)
        
    @property
    def update_count(self) -> int:
        """Returns the number of updates currently stored."""
        return len(self.updates)
        
    @property
    def spreadsheet_url(self) -> str:
        """Returns the URL to the Google Spreadsheet."""
        return f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/edit"
        
    @property
    def csv_export_url(self) -> str:
        """Returns the CSV export URL for the spreadsheet."""
        base_url = f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/export?format=csv"
        if self.sheet_gid:
            return f"{base_url}&gid={self.sheet_gid}"
        return base_url
    
    def get_recent_updates(self, limit: int = 5) -> List[Update]:
        """
        Get the most recent updates.
        
        Args:
            limit: Maximum number of updates to return
            
        Returns:
            List of the most recent updates (already sorted by date, newest first)
        """
        return self.updates[:limit]
    
    def get_all_updates(self) -> List[Update]:
        """
        Get all updates.
        
        Returns:
            List of all updates (already sorted by date, newest first)
        """
        return self.updates
    
    def get_updates_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Update]:
        """
        Get updates within a specific date range.
        
        Args:
            start_date: The start date (inclusive)
            end_date: The end date (inclusive)
            
        Returns:
            List of updates within the specified date range
        """
        return [
            update for update in self.updates 
            if start_date <= update.date <= end_date
        ]
    
    def load_from_spreadsheet(self, date_column: str = 'Date', content_column: str = 'Content', 
                             date_format: Optional[str] = None, dayfirst: bool = True):
        """
        Load updates from the Google Spreadsheet using pandas and the CSV export URL.
        
        Args:
            date_column: Name of the column containing dates
            content_column: Name of the column containing update content
            date_format: Optional explicit date format string (e.g., '%d/%m/%Y')
            dayfirst: Whether the date format has day before month (e.g., 31/12/2023 vs 12/31/2023)
        
        Returns:
            The number of updates loaded
        """
        try:
            # Load the CSV directly using pandas
            self.logger.info(f"Loading updates from spreadsheet URL: {self.csv_export_url}")
            df = pd.read_csv(self.csv_export_url)
            
            # Check if required columns exist
            if date_column not in df.columns or content_column not in df.columns:
                available_columns = ', '.join(df.columns)
                self.logger.error(f"Required columns not found. Available columns: {available_columns}")
                raise ValueError(f"Required columns {date_column} and/or {content_column} not found in spreadsheet")
            
            # Process the data
            self.updates = []
            
            # Convert date column to datetime with explicit format if provided
            if not pd.api.types.is_datetime64_any_dtype(df[date_column]):
                if date_format:
                    # Use explicit format if provided
                    df[date_column] = pd.to_datetime(df[date_column], format=date_format, errors='coerce')
                else:
                    # Otherwise use pandas inference with dayfirst parameter
                    df[date_column] = pd.to_datetime(df[date_column], dayfirst=dayfirst, errors='coerce')
            
            # Drop rows with invalid dates
            df = df.dropna(subset=[date_column])
            
            # Create Update objects
            for _, row in df.iterrows():
                try:
                    date = row[date_column]
                    # Convert pandas timestamp to Python datetime if needed
                    if isinstance(date, pd.Timestamp):
                        date = date.to_pydatetime()
                    content = row[content_column]
                    self.updates.append(Update(date=date, content=content))
                except Exception as e:
                    self.logger.warning(f"Error processing row {row}: {e}")
            
            # Sort updates by date (newest first)
            self._sort_updates()
            self.logger.info(f"Loaded {len(self.updates)} updates from spreadsheet")
            return len(self.updates)
            
        except Exception as e:
            self.logger.error(f"Error loading spreadsheet: {e}")
            raise
    
    def _sort_updates(self) -> None:
        """Sort updates by date in descending order (newest first)."""
        self.updates.sort(key=lambda update: update.date, reverse=True)


# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO, 
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Use the actual spreadsheet ID
    reader = UpdateReader("1P3W_ybjMBduJWohitdB5fdXZEqrknS25FzYmMkxqmG0")
    
    # Load updates from the spreadsheet with explicit date handling
    # Use dayfirst=True if dates are in DD/MM/YYYY format
    reader.load_from_spreadsheet(date_format='%d/%m/%Y', dayfirst=True)
    
    # Alternative: if you don't know the format exactly but know day comes first
    # reader.load_from_spreadsheet(dayfirst=True)
    
    # Print total number of updates
    print(f"Total updates: {reader.update_count}")
    
    # Print recent updates
    print("\nRecent updates:")
    for update in reader.get_recent_updates(5):
        print(update)