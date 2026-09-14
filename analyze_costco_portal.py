#!/usr/bin/env python3
"""
Analyze Costco WiFi portal structure
Run this script when connected to Costco WiFi to capture portal details
"""

import requests
import re
from urllib.parse import urlparse, parse_qs

def analyze_portal():
    print("=== Costco WiFi Portal Analysis ===\n")
    
    # Test for captive portal by making a request
    try:
        # This should redirect to the portal
        response = requests.get('http://detectportal.firefox.com/canonical.html', 
                              allow_redirects=False, timeout=5)
        
        print(f"Response Code: {response.status_code}")
        
        if response.status_code in [302, 307]:
            location = response.headers.get('Location', '')
            print(f"Redirect Location: {location}")
            
            # Extract gateway IP
            if 'http://' in location:
                gateway = location.split('/')[2]
                print(f"Gateway IP: {gateway}")
            
            # Now fetch the portal page
            try:
                portal_response = requests.get(location, timeout=5)
                print(f"\nPortal Page Status: {portal_response.status_code}")
                
                # Look for forms
                forms = re.findall(r'<form[^>]*>(.*?)</form>', portal_response.text, re.DOTALL)
                print(f"\nFound {len(forms)} form(s)")
                
                for i, form in enumerate(forms):
                    print(f"\n--- Form {i+1} ---")
                    
                    # Extract form action
                    action_match = re.search(r'action=["\']([^"\']+)["\']', form, re.IGNORECASE)
                    if action_match:
                        print(f"Action: {action_match.group(1)}")
                    
                    # Extract method
                    method_match = re.search(r'method=["\']([^"\']+)["\']', form, re.IGNORECASE)
                    if method_match:
                        print(f"Method: {method_match.group(1)}")
                    
                    # Look for checkboxes
                    checkboxes = re.findall(r'<input[^>]*type=["\']checkbox["\'][^>]*>', form, re.IGNORECASE)
                    if checkboxes:
                        print(f"Checkboxes found: {len(checkboxes)}")
                        for cb in checkboxes:
                            name_match = re.search(r'name=["\']([^"\']+)["\']', cb)
                            if name_match:
                                print(f"  Checkbox name: {name_match.group(1)}")
                    
                    # Look for submit buttons
                    submits = re.findall(r'<input[^>]*type=["\']submit["\'][^>]*>', form, re.IGNORECASE)
                    if submits:
                        print(f"Submit buttons: {len(submits)}")
                        for sb in submits:
                            name_match = re.search(r'name=["\']([^"\']+)["\']', sb)
                            value_match = re.search(r'value=["\']([^"\']*)["\']', sb)
                            print(f"  Button: name={name_match.group(1) if name_match else 'N/A'}, "
                                  f"value={value_match.group(1) if value_match else 'N/A'}")
                    
                    # Look for hidden fields
                    hiddens = re.findall(r'<input[^>]*type=["\']hidden["\'][^>]*>', form, re.IGNORECASE)
                    if hiddens:
                        print(f"Hidden fields: {len(hiddens)}")
                        for hf in hiddens:
                            name_match = re.search(r'name=["\']([^"\']+)["\']', hf)
                            value_match = re.search(r'value=["\']([^"\']*)["\']', hf)
                            if name_match:
                                print(f"  Hidden: {name_match.group(1)}={value_match.group(1) if value_match else ''}")
                
                # Save the full HTML for manual inspection
                with open('/tmp/costco_portal.html', 'w') as f:
                    f.write(portal_response.text)
                print(f"\nFull HTML saved to: /tmp/costco_portal.html")
                
            except Exception as e:
                print(f"Error fetching portal page: {e}")
        
        else:
            print("No redirect detected - may already be connected to internet")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_portal()
