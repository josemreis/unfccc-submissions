import time
from datetime import datetime
from typing import Optional
import os
import json
import re
import pandas as pd
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

# constants
DEBUG = True
MIN_SUBMISSIONS_SANITY_CHECK = 486
MAX_RETRIES = 3
SHORT_SLEEP = 3
LONG_SLEEP = 10
DEFAULT_TIMEOUT = 20
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
HEADLESS = False
LOG_PATH = (
    os.devnull
)  # this will supress any log file, for an actuall log file replace it with its path


def deploy_firefox(
    path_to_geckodriver: str or None = "resources/geckodriver",
    headless: bool = HEADLESS,
    **kwargs,
) -> webdriver.Firefox:
    """
    launches a firefox browser instance
    """
    firefox_ops = Options()
    if headless:
        firefox_ops.add_argument("-headless")
    driver = webdriver.Firefox(
        executable_path=path_to_geckodriver,
        options=firefox_ops,
        service_log_path=LOG_PATH,
        **kwargs,
    )
    return driver


def kill_webdriver(driver: webdriver.Firefox) -> None:
    """Kill the webdriver"""
    driver.close()
    driver.quit()


def minimum_of_submissions_sanity_check(
    driver: webdriver.Firefox,
    min_heuristic: int = MIN_SUBMISSIONS_SANITY_CHECK,
) -> bool:
    """
    The web server loads varying numbers of docs some times. Refreshing it seems to help.
    After several repetitions the constant MIN_SUBMISSIONS_SANITY_CHECK was the correct value in 07/06/2022.
    If below this number, throw a False.
    """
    panel_titles = driver.find_elements(
        By.XPATH, "//div[@class = 'panel-group']//a[@class = 'collapsed']"
    )
    doc_count = 0
    for title in panel_titles:
        n = re.search(r"(?<=\()[0-9]+(?=\))", title.text)
        if n:
            doc_count += int(n.group(0))
        else:
            return False
    return doc_count >= min_heuristic


def _visit_main_page(driver: webdriver.Firefox) -> None:
    """
    Visit the main page and open the submissions panels
    """
    driver.get(SUBMISSIONS_URL)
    time.sleep(SHORT_SLEEP)
    # clear tags
    tags_btn = driver.find_element(By.ID, "btnClearTags")
    tags_btn.click()
    time.sleep(LONG_SLEEP)
    WebDriverWait(driver, DEFAULT_TIMEOUT).until(
        EC.presence_of_element_located(
            (By.XPATH, "//div[@class = 'panel-group']//a[@class = 'collapsed']")
        )
    )


def visit_main_page(driver: webdriver.Firefox) -> None:
    """Visit the main page and check if the number of documents displayed by the web-server passes doc count sanity check"""
    _visit_main_page(driver)
    # sanity check
    i = 0
    while not minimum_of_submissions_sanity_check(driver, MIN_SUBMISSIONS_SANITY_CHECK):
        _visit_main_page(driver)
        i += 1
        if i > MAX_RETRIES:
            raise ValueError(
                "Web server is loading a very small number of documents, data is not trust worthy"
            )
        else:   
            time.sleep(LONG_SLEEP)
            


def _open_submission_panel(
    driver: webdriver.Firefox, panel_button: webdriver.remote.webelement.WebElement,
    debug: bool = DEBUG
) -> None:
    """
    Open a submission panel. Note: both cannot be opened at the same time.
    """
    i = 0
    while True:
        try:
            panel_button.click()
            break
        except Exception as e:
            if debug:
                print(e)
            if i > DEFAULT_TIMEOUT:
                raise ValueError(
                    f"Submission panel buttons are not clickable. Timed out at {DEFAULT_TIMEOUT} secs."
                )
            else:
                time.sleep(SHORT_SLEEP)
                i += 1
    # wait for the panel to open
    WebDriverWait(driver, DEFAULT_TIMEOUT).until(
        EC.presence_of_element_located(
            (By.XPATH, "//div[@class = 'submissioncallarea']")
        )
    )


def open_submission_panel(
    driver: webdriver.Firefox,
    panel_button: webdriver.remote.webelement.WebElement,
    max_attempts: int = MAX_RETRIES,
    debug: bool = DEBUG
) -> None:
    """wrapper around _open_submission_panel for cases in which the data is not loaded before a refresh (hacky solution...)"""
    # check if the submissions were loaded
    attempt = 0
    while True:
        try:
            _open_submission_panel(driver, panel_button)
            WebDriverWait(driver, SHORT_SLEEP).until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        "//div[@class = 'submissioncallarea']/div//div[@class = 'col-md-10 issue']",
                    )
                )
            )
            break
        except Exception as e:
            if debug:  
                print(e)
            if attempt < max_attempts:
                visit_main_page(driver)
                time.sleep(LONG_SLEEP)
                attempt += 1
            else:
                raise ValueError(
                    f"Submissions data was not loaded to the panel after clicking on it after {max_attempts} attempts."
                )


def find_text_element(
    elem: webdriver.remote.webelement.WebElement, xpath: str
) -> Optional[str]:
    """
    Error handling friendly find_element().text so that it returns a None object if webelement is missing
    """
    try:
        return elem.find_element(
            By.XPATH,
            xpath,
        ).text
    except NoSuchElementException:
        pass


def _parse_submissions(driver: webdriver.Firefox) -> list:
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


def parse_submissions(driver: webdriver.Firefox) -> dict:
    """
    Wrapper around _parse_submissions for pagination
    """
    # Open the current and previous submissions panels sequentially
    panel_buttons = driver.find_elements(
        By.XPATH, "//div[@class = 'panel-group']//a[@class = 'collapsed']"
    )
    subs_container = []
    for panel_button in panel_buttons:
        open_submission_panel(driver, panel_button)
        while True:
            subs_container.extend(_parse_submissions(driver))
            try:
                # next page
                nxt = driver.find_element(
                    By.XPATH, "//a[contains(@onclick, '.GoToNextPage()')]"
                )
                nxt.click()
            except:
                break
            WebDriverWait(driver, DEFAULT_TIMEOUT).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[@class = 'submissioncallarea']")
                )
            )
            driver.execute_script("window.scrollTo(0,document.body.scrollHeight)")
            time.sleep(SHORT_SLEEP)
    # add the query metadata and return
    return {
        "data_source": SUBMISSIONS_URL,
        "collected_at": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
        "submissions_data": subs_container,
    }


def write_to_json(submissions_data: list, data_dir: str = "data") -> None:
    """write to data dir as json"""
    with open(os.path.join(data_dir, "submissions_data.json"), "w") as f:
        json.dump(submissions_data, f, indent=4)


def write_to_csv(submissions_data: list, data_dir: str = "data") -> None:
    """write to data dir as csv"""
    container = []
    submissions_all = submissions_data.pop("submissions_data")
    for issue in submissions_all:
        if "submissions" in issue:
            # add the data collection metadata
            new_keys = [
                f"issue_{_}" if _ not in ["issue", "submissions"] else _ for _ in issue
            ]
            issue = {k: v for k, v in zip(new_keys, issue.values())}
            issue = {**issue, **submissions_data}
            issue_specific_submissions = issue.pop("submissions")
            for (
                submission_entity_type,
                submission_list,
            ) in issue_specific_submissions.items():
                for submission_metadata in submission_list:
                    submission_metadata["entity_type"] = submission_entity_type
                    container.append({**submission_metadata, **issue})
    df = pd.DataFrame(container)
    df.to_csv(os.path.join(data_dir, "submissions_data.csv"))


def main(**kwargs) -> None:
    driver = deploy_firefox(**kwargs)
    visit_main_page(driver)
    submissions_data = parse_submissions(driver)
    if not os.path.isdir("data"):
        os.mkdir("data")
    write_to_json(submissions_data, data_dir="data")
    write_to_csv(submissions_data, data_dir="data")
    kill_webdriver(driver)


if __name__ == "__main__":
    main()
