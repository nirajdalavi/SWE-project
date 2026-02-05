"""
UI Automation Service
Handles browser automation, DOM analysis, and screenshot processing for ElevenLabs webhook.
"""

import json
import base64
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import cv2
import numpy as np
from PIL import Image
import io

logger = logging.getLogger(__name__)

class UIAutomationService:
    """Service for automating UI interactions based on ElevenLabs requests."""
    
    def __init__(self):
        self.driver = None
        self.wait_timeout = 10
        
    def _setup_driver(self, headless: bool = True) -> webdriver.Chrome:
        """Setup Chrome driver with appropriate options."""
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        try:
            driver = webdriver.Chrome(options=chrome_options)
            driver.implicitly_wait(self.wait_timeout)
            return driver
        except Exception as e:
            logger.error(f"Failed to setup Chrome driver: {e}")
            raise
    
    def _take_screenshot(self) -> str:
        """Take a screenshot and return as base64 string."""
        try:
            screenshot = self.driver.get_screenshot_as_png()
            screenshot_b64 = base64.b64encode(screenshot).decode('utf-8')
            return f"data:image/png;base64,{screenshot_b64}"
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            return ""
    
    def _analyze_dom_snapshot(self, dom_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze DOM snapshot to understand page structure."""
        analysis = {
            "input_fields": [],
            "buttons": [],
            "links": [],
            "forms": [],
            "total_elements": 0
        }
        
        try:
            if "inputs" in dom_snapshot:
                for input_elem in dom_snapshot["inputs"]:
                    selector = input_elem.get("selector", "")
                    input_type = input_elem.get("type", "text")
                    analysis["input_fields"].append({
                        "selector": selector,
                        "type": input_type,
                        "found": False
                    })
            
            # Count total elements on page
            elements = self.driver.find_elements(By.XPATH, "//*")
            analysis["total_elements"] = len(elements)
            
        except Exception as e:
            logger.error(f"Failed to analyze DOM snapshot: {e}")
            
        return analysis
    
    def _find_element_by_selector(self, selector: str) -> Optional[Any]:
        """Find element using various selector strategies."""
        try:
            # Try CSS selector first
            if selector.startswith("[") and "]" in selector:
                return self.driver.find_element(By.CSS_SELECTOR, selector)
            # Try XPath
            elif selector.startswith("//") or selector.startswith("/"):
                return self.driver.find_element(By.XPATH, selector)
            # Try ID
            elif selector.startswith("#"):
                return self.driver.find_element(By.ID, selector[1:])
            # Try class
            elif selector.startswith("."):
                return self.driver.find_element(By.CLASS_NAME, selector[1:])
            # Default to CSS selector
            else:
                return self.driver.find_element(By.CSS_SELECTOR, selector)
        except NoSuchElementException:
            logger.warning(f"Element not found with selector: {selector}")
            return None
        except Exception as e:
            logger.error(f"Error finding element {selector}: {e}")
            return None
    
    def _execute_intent(self, intent: str, dom_snapshot: Dict[str, Any], page_url: str) -> Dict[str, Any]:
        """Execute the specified UI intent."""
        result = {
            "intent": intent,
            "success": False,
            "actions_performed": [],
            "errors": [],
            "screenshots": []
        }
        
        try:
            # Navigate to the page
            self.driver.get(page_url)
            result["actions_performed"].append(f"Navigated to {page_url}")
            
            # Take initial screenshot
            initial_screenshot = self._take_screenshot()
            result["screenshots"].append({
                "stage": "initial",
                "screenshot": initial_screenshot
            })
            
            # Wait for page to load
            WebDriverWait(self.driver, self.wait_timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Process different intents
            if intent == "fill-login":
                result = self._handle_fill_login_intent(dom_snapshot, result)
            elif intent == "click-button":
                result = self._handle_click_button_intent(dom_snapshot, result)
            elif intent == "fill-form":
                result = self._handle_fill_form_intent(dom_snapshot, result)
            elif intent == "navigate":
                result = self._handle_navigate_intent(dom_snapshot, result)
            else:
                result["errors"].append(f"Unknown intent: {intent}")
                return result
            
            # Take final screenshot
            final_screenshot = self._take_screenshot()
            result["screenshots"].append({
                "stage": "final",
                "screenshot": final_screenshot
            })
            
            result["success"] = len(result["errors"]) == 0
            
        except Exception as e:
            logger.error(f"Error executing intent {intent}: {e}")
            result["errors"].append(str(e))
            
        return result
    
    def _handle_fill_login_intent(self, dom_snapshot: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        """Handle fill-login intent."""
        try:
            if "inputs" in dom_snapshot:
                for input_elem in dom_snapshot["inputs"]:
                    selector = input_elem.get("selector", "")
                    if not selector:
                        continue
                        
                    element = self._find_element_by_selector(selector)
                    if element:
                        # Determine what to fill based on selector or input type
                        if "email" in selector.lower() or "username" in selector.lower():
                            element.clear()
                            element.send_keys("test@example.com")
                            result["actions_performed"].append(f"Filled email field: {selector}")
                        elif "password" in selector.lower():
                            element.clear()
                            element.send_keys("testpassword123")
                            result["actions_performed"].append(f"Filled password field: {selector}")
                        else:
                            element.clear()
                            element.send_keys("test input")
                            result["actions_performed"].append(f"Filled field: {selector}")
                    else:
                        result["errors"].append(f"Could not find element: {selector}")
                        
        except Exception as e:
            result["errors"].append(f"Error in fill-login: {e}")
            
        return result
    
    def _handle_click_button_intent(self, dom_snapshot: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        """Handle click-button intent."""
        try:
            if "buttons" in dom_snapshot:
                for button_elem in dom_snapshot["buttons"]:
                    selector = button_elem.get("selector", "")
                    if not selector:
                        continue
                        
                    element = self._find_element_by_selector(selector)
                    if element:
                        element.click()
                        result["actions_performed"].append(f"Clicked button: {selector}")
                    else:
                        result["errors"].append(f"Could not find button: {selector}")
                        
        except Exception as e:
            result["errors"].append(f"Error in click-button: {e}")
            
        return result
    
    def _handle_fill_form_intent(self, dom_snapshot: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        """Handle fill-form intent."""
        try:
            if "inputs" in dom_snapshot:
                for input_elem in dom_snapshot["inputs"]:
                    selector = input_elem.get("selector", "")
                    if not selector:
                        continue
                        
                    element = self._find_element_by_selector(selector)
                    if element:
                        element.clear()
                        element.send_keys("test form data")
                        result["actions_performed"].append(f"Filled form field: {selector}")
                    else:
                        result["errors"].append(f"Could not find form field: {selector}")
                        
        except Exception as e:
            result["errors"].append(f"Error in fill-form: {e}")
            
        return result
    
    def _handle_navigate_intent(self, dom_snapshot: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        """Handle navigate intent."""
        try:
            if "links" in dom_snapshot:
                for link_elem in dom_snapshot["links"]:
                    selector = link_elem.get("selector", "")
                    if not selector:
                        continue
                        
                    element = self._find_element_by_selector(selector)
                    if element:
                        element.click()
                        result["actions_performed"].append(f"Clicked link: {selector}")
                    else:
                        result["errors"].append(f"Could not find link: {selector}")
                        
        except Exception as e:
            result["errors"].append(f"Error in navigate: {e}")
            
        return result
    
    def process_ui_flow(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Main method to process UI flow requests."""
        start_time = time.time()
        
        result = {
            "status": "processing",
            "intent": payload.get("intent"),
            "session_id": payload.get("session_id"),
            "user_id": payload.get("user_id"),
            "tool_invocation_id": payload.get("tool_invocation_id"),
            "page_url": payload.get("page_url"),
            "processed_at": datetime.now().isoformat(),
            "automation_result": {},
            "processing_time": 0,
            "success": False,
            "error": None
        }
        
        try:
            # Setup browser
            self.driver = self._setup_driver(headless=True)
            
            # Analyze DOM snapshot
            dom_analysis = self._analyze_dom_snapshot(payload.get("dom_snapshot", {}))
            
            # Execute the intent
            automation_result = self._execute_intent(
                payload.get("intent", ""),
                payload.get("dom_snapshot", {}),
                payload.get("page_url", "")
            )
            
            result["automation_result"] = automation_result
            result["dom_analysis"] = dom_analysis
            result["success"] = automation_result.get("success", False)
            
        except Exception as e:
            logger.error(f"Error in process_ui_flow: {e}")
            result["error"] = str(e)
            result["success"] = False
            
        finally:
            # Cleanup
            if self.driver:
                self.driver.quit()
                
        result["processing_time"] = time.time() - start_time
        result["status"] = "completed" if result["success"] else "failed"
        
        return result
