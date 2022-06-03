import time
from pathlib import Path
from typing import Callable, Optional
import os
import json
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

# constants
SUBMISSIONS_URL = "https://www4.unfccc.int/sites/submissionsstaging/Pages/Home.aspx"
RELEVANT_ENTITY_TYPES = [
    "IGO",
    "NAO",
    "NGO",
    "Elections Chairs and Coordinators",
    "Party",
    "UN",
    "Observer State",
]
HEADLESS = True


def deploy_firefox(
    path_to_geckodriver: str or None = "resources/geckodriver",
    headless: bool = HEADLESS,
    **kwargs
) -> webdriver.Firefox:
    """
    launches a firefox instance using the same browser version as in OpenWPM
    """
    firefox_ops = Options()
    if headless:
        firefox_ops.add_argument("-headless")
    driver = webdriver.Firefox(
        executable_path=path_to_geckodriver,
        options=firefox_ops,
        service_log_path=os.devnull,
        **kwargs
    )
    return driver


def kill_webdriver(driver: webdriver.Firefox) -> None:
    """Kill the webdriver"""
    driver.close()
    driver.quit()


def visit_main_page(driver: webdriver.Firefox) -> None:
    """Visit the main page and open submissions panels"""
    driver.get(SUBMISSIONS_URL)
    time.sleep(3)
    # # clear tags
    # tags_btn = driver.find_element(By.ID, "btnClearTags")
    # tags_btn.click()
    # wait for the panel button
    element = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//h4[@class = 'panel-title']/a[@class = 'collapsed']")
        )
    )
    element.click()
    # wait for the panel to open
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located(
            (By.XPATH, "//div[@class = 'submissioncallarea']")
        )
    )


def find_text_element(elem, xpath: str) -> str:
    """error handling friendly find_element().text"""
    try:
        return elem.find_element(
            By.XPATH,
            xpath,
        ).text
    except NoSuchElementException:  
        pass


def _parse_submissions(driver: webdriver.Firefox) -> None:
    """Parse a submission div element"""
    submission_grids = driver.find_elements(
        By.XPATH,
        "//div[@class = 'panel-collapse collapse in']//div[@class = 'soby_gridcell ']",
    )
    submission_list = []
    for submission_grid in submission_grids:
        sub_dict = {}
        sub_dict["issue"] = find_text_element(
            submission_grid,
            ".//div[@class = 'submissioncallarea']/div//div[@class = 'col-md-10 issue']",
        )
        sub_dict["deadline"] = find_text_element(
            submission_grid,
            ".//div[@class = 'submissioncallarea']/div//div[@class = 'col-md-7 deadline']",
        )
        sub_dict["title"] = find_text_element(
            submission_grid,
            ".//div[@class = 'submissioncallarea']/div//div[@class = 'col-md-10 cfstitle']",
        )
        sub_dict["mandate"] = find_text_element(
            submission_grid,
            ".//div[@class = 'submissioncallarea']/div//div[@class = 'col-md-10 mandate']",
        )
        submission_sections = submission_grid.find_elements(
            By.XPATH,
            ".//div[@class = 'container submissionarea']/div[@class = 'submissionssection']",
        )
        sub_dict["submissions"] = {}
        for submission_section in submission_sections:
            entity_type = submission_section.get_attribute("entitytype")
            if entity_type in RELEVANT_ENTITY_TYPES:
                sub_dict["submissions"][entity_type] = []
                submissions = submission_section.find_elements(
                    By.XPATH, ".//div[contains(@class, 'row tablefilerow ')]"
                )
                if submissions:
                    for submission in submissions:
                        sub_url = driver.current_url.replace(
                            "/sites/submissionsstaging/Pages/Home.aspx",
                            submission.get_attribute("fileref"),
                        )
                        sub_dict["submissions"][entity_type].append(
                            {
                                "submission_name": find_text_element(
                                    submission, ".//div[@class = 'col-sm-4 filename']"
                                ),
                                "submission_entity": find_text_element(
                                    submission, ".//div[@class = 'col-sm-4 entity']"
                                ),
                                "submission_language": find_text_element(
                                    submission, ".//div[@class = 'col-sm-2 language']"
                                ),
                                "submission_date": find_text_element(
                                    submission,
                                    ".//div[@class = 'col-sm-2 submissiondate']",
                                ),
                                "submission_url": sub_url,
                            }
                        )
        submission_list.append(sub_dict)
    return submission_list


def parse_submissions(driver: webdriver.Firefox) -> None:
    """Wrapper around _parse_submissions for pagination"""
    out = []
    while True:
        out.extend(_parse_submissions(driver))
        try:
            # next page
            nxt = driver.find_element(
                By.XPATH, "//a[contains(@onclick, '.GoToNextPage()')]"
            )
            nxt.click()
        except:
            break
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(
                (By.XPATH, "//div[@class = 'submissioncallarea']")
            )
        )
        driver.execute_script("window.scrollTo(0,document.body.scrollHeight)")
        time.sleep(3)
    return out

def export(submissions_data: list) -> None:
    """write to data dir"""
    if not os.path.isdir("data"):
        os.mkdir("data")
    with open("data/submissions_data.json", "w") as f:
        json.dump(submissions_data, f, indent=4)


def main() -> None:
    driver = deploy_firefox(log_path=os.path.devnull)
    visit_main_page(driver)
    submissions_data = parse_submissions(driver)
    export(submissions_data)
    kill_webdriver(driver)


if __name__ == "__main__":
    main()
