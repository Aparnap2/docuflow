import os
import json
from typing import Dict, Any, List
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request


class GoogleSheetsIntegration:
    def __init__(self):
        self.scopes = ['https://www.googleapis.com/auth/spreadsheets']
    
    def get_credentials(self, access_token: str, refresh_token: str = None):
        """Create credentials object from stored tokens"""
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            scopes=self.scopes
        )
        return creds
    
    def sync_to_sheet(self, 
                     access_token: str, 
                     refresh_token: str, 
                     spreadsheet_id: str, 
                     range_name: str, 
                     extracted_data: Dict[str, Any],
                     schema: List[Dict[str, str]] = None) -> bool:
        """
        Sync extracted data to Google Sheets
        
        Args:
            access_token: Google OAuth access token
            refresh_token: Google OAuth refresh token
            spreadsheet_id: Google Sheets spreadsheet ID
            range_name: A1 notation range (e.g. 'Sheet1!A1')
            extracted_data: Data extracted by the engine
            schema: Schema definition to map fields to columns
        """
        try:
            creds = self.get_credentials(access_token, refresh_token)
            
            # Build the service
            service = build('sheets', 'v4', credentials=creds)
            
            # Prepare values for the sheet
            if schema:
                # Use schema to determine the order of values
                ordered_values = []
                for field in schema:
                    key = field['key']
                    if key in extracted_data:
                        value = extracted_data[key]
                        # Convert to string representation for spreadsheet
                        if isinstance(value, (list, dict)):
                            ordered_values.append(json.dumps(value))
                        else:
                            ordered_values.append(str(value))
                    else:
                        ordered_values.append("")  # Empty cell for missing values
                values = [ordered_values]
            else:
                # If no schema, extract values in arbitrary order
                values = [[str(v) for v in extracted_data.values()]]
            
            # Prepare the request body
            body = {
                'values': values
            }
            
            # Make the API call
            result = service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                body=body
            ).execute()
            
            print(f"{result.get('updates', {}).get('updatedCells', 0)} cells updated.")
            return True
            
        except HttpError as error:
            print(f"An error occurred: {error}")
            return False
        except Exception as error:
            print(f"An unexpected error occurred: {error}")
            return False
    
    def create_sheet(self, access_token: str, refresh_token: str, title: str) -> Dict[str, Any]:
        """Create a new spreadsheet"""
        try:
            creds = self.get_credentials(access_token, refresh_token)
            service = build('sheets', 'v4', credentials=creds)
            
            spreadsheet = {
                'properties': {
                    'title': title
                }
            }
            
            spreadsheet = service.spreadsheets().create(body=spreadsheet,
                                                      fields='spreadsheetId').execute()
            
            print(f"Spreadsheet ID: {spreadsheet.get('spreadsheetId')}")
            return {
                "spreadsheet_id": spreadsheet.get('spreadsheetId'),
                "title": title
            }
            
        except HttpError as error:
            print(f"An error occurred: {error}")
            return {}
    
    def get_spreadsheet_info(self, access_token: str, refresh_token: str, spreadsheet_id: str) -> Dict[str, Any]:
        """Get information about a specific spreadsheet"""
        try:
            creds = self.get_credentials(access_token, refresh_token)
            service = build('sheets', 'v4', credentials=creds)
            
            spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            
            return {
                "spreadsheet_id": spreadsheet_id,
                "title": spreadsheet['properties']['title'],
                "sheets": [sheet['properties'] for sheet in spreadsheet['sheets']]
            }
            
        except HttpError as error:
            print(f"An error occurred: {error}")
            return {}