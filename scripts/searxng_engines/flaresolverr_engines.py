# SPDX-License-Identifier: AGPL-3.0-or-later
"""FlareSolverr-backed search engines (DDG, Brave, Bing).

Routes the search through a FlareSolverr instance (real browser, solves
challenges), then parses the returned HTML with lxml.
"""

from urllib.parse import quote_plus, urlparse, parse_qs, unquote
from lxml import html
import json

about = {
    "website": "https://github.com/FlareSolverr/FlareSolverr",
    "wikidata_id": None,
    "official_api_documentation": "https://github.com/FlareSolverr/FlareSolverr",
    "use_official_api": False,
    "require_api_key": False,
    "results": "HTML",
}

categories = ["general"]
paging = False

SITES = {
    "ddg": {
        "url": "https://html.duckduckgo.com/html/?q={q}",
        "results_xpath": "//div[contains(@class,'results_links')]",
        "url_xpath": ".//a[contains(@class,'result__a')]/@href",
        "title_xpath": ".//a[contains(@class,'result__a')]",
        "content_xpath": ".//a[contains(@class,'result__snippet')]",
    },
    "brave": {
        "url": "https://search.brave.com/search?q={q}&source=web",
        "results_xpath": "//div[@data-type='web']",
        "url_xpath": ".//div[contains(@class,'search-snippet-title')]//ancestor::a[1]/@href",
        "title_xpath": ".//div[contains(@class,'search-snippet-title')]",
        "content_xpath": ".//div[contains(@class,'snippet-description')] | .//div[contains(@class,'snippet-content')] | .//div[contains(@class,'result-content')]//div[contains(@class,'desktop-default-regular')]",
    },
    "bing": {
        "url": "https://www.bing.com/search?q={q}&mkt=en-US&setlang=en-us",
        "results_xpath": "//li[contains(@class,'b_algo')]",
        "url_xpath": ".//h2/a/@href",
        "title_xpath": ".//h2/a",
        "content_xpath": ".//div[contains(@class,'b_caption')]//p | .//p",
    },
}

flaresolverr_url = "http://odysseus-flaresolverr:8191/v1"
site = "ddg"


def _cfg():
    return SITES.get(site, SITES["ddg"])


def _unwrap_ddg(url):
    """DDG wraps results in //duckduckgo.com/l/?uddg=<real-url>."""
    if "duckduckgo.com/l/" in url or url.startswith("//duckduckgo.com"):
        try:
            qs = parse_qs(urlparse(url if url.startswith("http") else "https:" + url).query)
            if "uddg" in qs:
                return unquote(qs["uddg"][0])
        except Exception:
            pass
    return url


def request(query, params):
    cfg = _cfg()
    target = cfg["url"].format(q=quote_plus(query))
    params["method"] = "POST"
    params["url"] = flaresolverr_url
    params["headers"]["Content-Type"] = "application/json"
    params["data"] = json.dumps({
        "cmd": "request.get",
        "url": target,
        "maxTimeout": 55000,
    })
    params["raise_for_httperror"] = False
    return params


def _text(el):
    return el.text_content().strip() if hasattr(el, "text_content") else str(el).strip()


def response(resp):
    cfg = _cfg()
    results = []
    try:
        payload = json.loads(resp.text)
    except Exception:
        return results
    body = (payload.get("solution") or {}).get("response") or ""
    if not body:
        return results
    try:
        dom = html.fromstring(body)
    except Exception:
        return results
    for node in dom.xpath(cfg["results_xpath"]):
        urls = node.xpath(cfg["url_xpath"])
        titles = node.xpath(cfg["title_xpath"])
        if not urls or not titles:
            continue
        url = urls[0]
        title = _text(titles[0])
        if not title:
            continue
        if site == "ddg":
            url = _unwrap_ddg(url)
        if url.startswith("//"):
            url = "https:" + url
        if not url.startswith("http"):
            continue
        content_parts = node.xpath(cfg["content_xpath"])
        content = _text(content_parts[0]) if content_parts else ""
        results.append({"url": url, "title": title, "content": content})
    return results
