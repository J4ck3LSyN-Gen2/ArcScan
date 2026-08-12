from __future__ import annotations

import argparse, logging, random, sys, time, json, csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone 
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
import requests # type: ignore
from requests.adapters import HTTPAdapter # type: ignore
from urllib3.util.retry import Retry # type: ignore 

__version__ = "0.1.2"
__author__ = "J4ck3LSyN"

class ArcFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\x1b[38;2;100;100;100m",
        logging.INFO: "\x1b[38;2;0;150;255m",
        logging.WARNING: "\x1b[33m",
        logging.ERROR: "\x1b[31m",
        logging.CRITICAL: "\x1b[41m\x1b[37m"
    }
    RESET = "\x1b[0m"

    def format(self, record):
        record.asctime = self.formatTime(record, self.datefmt)
        color = self.COLORS.get(record.levelno, self.COLORS[logging.INFO])
        return f"{self.COLORS[logging.DEBUG]}[{record.asctime}]{self.RESET} {color}{record.levelname:<8}{self.RESET} {record.getMessage()}"

logger = logging.getLogger("Arc")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(ArcFormatter(datefmt="%H:%M:%S"))
logger.addHandler(handler)

class ArcLogger:
    def __init__(self,name:str,verbosity:bool=True):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.verbosity = verbosity
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(ArcFormatter(datefmt="%H:%M:%S"))
            self.logger.addHandler(handler)

    def pipe(self,message:str,level:int|str=1,exc_info:bool=False,no_log:bool=False,silent:bool=False):
        if silent or not self.verbosity:
            return
            
        prefix_map = {1: "[*]", 2:"[+]" ,3: "[!]", 4:"[>]", 5:"[@]", "output": "[^] "}
        log_map = {
            0: self.logger.debug, 'd': self.logger.debug, 'debug': self.logger.debug,
            1: self.logger.info, 'i': self.logger.info, 'info': self.logger.info,
            2: self.logger.warning, 'w': self.logger.warning, 'warning': self.logger.warning,
            3: self.logger.error, 'r': self.logger.error, 'error': self.logger.error,
            4: self.logger.critical, 'c': self.logger.critical, 'critical': self.logger.critical}
        prefix = prefix_map.get(level, "")+" "
        lFunc = log_map.get(level, self.logger.info)
        if not no_log:
            lFunc(f"{prefix}{message}", exc_info=exc_info)

class ArcConfig:
    def __init__(self):
        self.SEARCH_URL = "https://www.arcgis.com/sharing/rest/search"
        self.ITEM_URL = "https://www.arcgis.com/sharing/rest/content/items/{item_id}"
        self.DASHBOARD_URL = "https://www.arcgis.com/apps/dashboards/{item_id}"
        self.MAX_PER_PAGE = 100          # ArcGIS hard limit
        self.DEFAULT_PAGE_SIZE = 50
        self.DEFAULT_TIMEOUT = 10.0
        self.DEFAULT_VERIFY_WORKERS = 8
        self.DEFAULT_DELAY = 0.15
        self.USERAGENTS:List[str]=['Mozilla/5.0 (Linux; U; Android 8.1.0; en-us; MI 6X Build/OPM1.171019.011) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/61.0.3163.128 Mobile Safari/537.36 XiaoMi/MiuiBrowser/9.5.14', 'Mozilla/5.0 (Linux; Android 9; LM-Q720 Build/PKQ1.190302.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/83.0.4103.101 Mobile Safari/537.36', 'Mozilla/5.0 (Linux; Android 10; SM-A217F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.116 Mobile Safari/537.36 EdgA/46.01.4.5140', 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 EdgiOS/46.3.26 Mobile/15E148 Safari/605.1.15', 'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.1; Trident/4.0; SLCC2; .NET CLR 2.0.50727; .NET CLR 3.5.30729; .NET CLR 3.0.30729; Tablet PC 2.0; Zoom 3.6.0)', 'Mozilla/5.0 (Linux; Android 9; vivo 2007 Build/PKQ1.190616.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.84 Mobile Safari/537.36 VivoBrowser/6.9.0.1', 'Dalvik/1.6.0 (Linux; U; Android 4.2.2; GT-S7275Y Build/JDQ39)', 'Mozilla/5.0 (Linux; Android 11; vivo 1901; wv) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.84 Mobile Safari/537.36 VivoBrowser/7.10.0.0', 'Mozilla/5.0 (Linux; Android 8.0.0; PIC-LX9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Mobile Safari/537.36', 'Dalvik/2.1.0 (Linux; U; Android 7.0; SM-J327R4 Build/NRD90M)', 'Mozilla/5.0 (Linux; Android 8.1.0; T3 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.101 Mobile Safari/537.36', 'Mozilla/5.0 (Linux; Android 5.1.1; 9022X) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.101 Safari/537.36', 'Dalvik/2.1.0 (Linux; U; Android 8.1.0; Panasonic P6 Build/O11019)', 'Mozilla/5.0 (Linux; Android 11; SM-T295) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36', 'Mozilla/5.0 (Linux; Android 6.0.1; SM-J700M) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.125 Mobile Safari/537.36', 'Mozilla/5.0 (Linux; Android 6.0.1; SAMSUNG SM-J700M) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/15.0 Chrome/90.0.4430.210 Mobile Safari/537.36', 'Mozilla/5.0 (Linux; Android 4.4.2; MicromaxP480) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36', 'Dalvik/2.1.0 (Linux; U; Android 9; VCE-L22 Build/HUAWEIVCE-L22)', 'Mozilla/5.0 (Linux; Android 11; SM-G973F Build/RP1A.200720.012; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/91.0.4472.88 Mobile Safari/537.36', 'Mozilla/5.0 (Linux; Android 8.1.0; LM-Q925K Build/OPM1.171019.026; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/94.0.4606.50 Mobile Safari/537.36;KAKAOTALK 2309520', 'Mozilla/5.0 (Linux; Android 11; M2007J3SG) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.62 Mobile Safari/537.36', 'Mozilla/5.0 (Linux; Android 10; EML-L09) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.152 Mobile Safari/537.36', 'Mozilla/5.0 (Linux; Android 8.1.0; SM-G610M) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36', 'Mozilla/5.0 (Linux; Android 8.1.0; SM-J260FU) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.96 Mobile Safari/537.36', 'Mozilla/5.0 (Linux; Android 7.0; CPN-W09 Build/HUAWEICPN-W09; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/93.0.4577.62 Mobile Safari/537.36', 'Mozilla/5.0 (Linux; Android 10; Surface Duo) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.116 Mobile Safari/537.36 EdgA/45.10.4.5088', 'Mozilla/5.0 (Linux; Android 10; Pixel 3 XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.101 Mobile Safari/537.36', 'Mozilla/5.0 (Linux; Android 9; SM-J730GM) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.111 Mobile Safari/537.36', 'Dalvik/2.1.0 (Linux; U; Android 6.0.1; Le X520 Build/IHXOSOP5801910311S)', 'Dalvik/2.1.0 (Linux; U; Android 9; 5006G Build/PPR1.180610.011)', 'Dalvik/2.1.0 (Linux; U; Android 7.0; Aura Sleek Plus Build/NRD90M)', 'Mozilla/5.0 (Linux; Android 11; Pixel 5 Build/RQ3A.210805.001.A1; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/92.0.4515.166 Mobile Safari/537.36', 'Mozilla/5.0 (Linux; Android 11; Pixel 4 XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Mobile Safari/537.36', 'Mozilla/5.0 (Linux; Android 10; U705AC) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Mobile Safari/537.36', 'Mozilla/5.0 (Linux; Android 9; SM-T865) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.101 Safari/537.36', 'Mozilla/5.0 (Linux; Android 8.0.0; Hi9Air) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.96 Safari/537.36', 'Mozilla/5.0 (Linux; Android 10; LG-US998 Build/QQ3A.200605.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/86.0.4208.3 Mobile Safari/537.36', 'Mozilla/5.0 (Linux; Android 10; RMX1821) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.185 Mobile Safari/537.36', 'Mozilla/5.0 (Linux; U; Android 8.1.0; es-us; Redmi 5 Plus Build/OPM1.171019.019) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/71.0.3578.141 Mobile Safari/537.36 XiaoMi/MiuiBrowser/12.5.2-go', 'Dalvik/2.1.0 (Linux; U; Android 8.1.0; Helio S60 Build/O11019)', 'Dalvik/2.1.0 (Linux; U; Android 10; SM-J700H Build/QQ3A.200805.001)', 'Mozilla/5.0 (Linux; Android 7.0; SM-J330F Build/NRD90M; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/64.0.3282.137 Mobile Safari/537.36 Viber/13.1.0.4', 'Dalvik/2.1.0 (Linux; U; Android 7.0; Ultra Sync Build/NRD90M)', 'Mozilla/5.0 (Linux; Android 11; CPH2021 Build/RP1A.200720.011; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/92.0.4515.159 Mobile Safari/537.36', 'Mozilla/5.0 (Linux; Android 9; MHA-L09) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.86 Mobile Safari/537.36', 'Mozilla/5.0 (Linux; Android 11; SM-N986U1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.101 Mobile Safari/537.36', 'Mozilla/5.0 (Linux; Android 8.0.0; STF-L09) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.101 Mobile Safari/537.36', 'Mozilla/5.0 (Linux; Android 10; moto g(7) plus) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.125 Mobile Safari/537.36', 'Dalvik/2.1.0 (Linux; U; Android 9; ASUS_X017D Build/PPR1.180610.009)', 'Mozilla/5.0 (Linux; arm_64; Android 10; SM-A307FN) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.132 YaApp_Android/10.92 YaSearchBrowser/10.92 BroPP/1.0 SA/1 Mobile Safari/537.36']
        self.OPERATIONAL_QUERIES:Dict[str,str] = {
            # --- Core  ---
            "vms": ('type:Dashboard ('
                '"Video Management System" OR '
                '"Skyline Video" OR '
                '"Security Camera" OR '
                '"Video Wall" OR '
                '"Camera Feed" OR '
                '"CCTV STATUS"'
                ')'
            ),
            "its": (
                'type:Dashboard "Traffic Control" OR "ITS" '
                'OR "Highway Cameras" OR "Transit Operations" OR "Traffic Management" '
                'OR "ATMS" OR "Signal Operations" OR "Traffic Signal" OR "Ramp Meter"'
            ),
            "ot": (
                'type:Dashboard "Operational Technology" OR "OT Security" OR "OT Network" '
                'OR "ICS Security" OR "Industrial IoT" OR "IIoT" OR "Edge Gateway" '
                'OR "Field Device" OR "Asset Inventory OT"'
            ),
            # --- Public safety, border, ICE ---
            "border": (
                'type:Dashboard "Border" OR "Port of Entry" OR "Customs" '
                'OR "Border Security" OR "Checkpoint" OR "CBP" OR "Border Patrol" '
                'OR "Border Operations" OR "Land Port"'
            ),
            "ice": (
                'type:Dashboard "ICE" OR "Immigration" OR "Customs Enforcement" '
                'OR "Detention Facility" OR "Removal Operations" OR "ERO" '
                'OR "Homeland Security Investigations" OR "HSI" OR "Immigration Enforcement" '
                'OR "Alien Tracking" OR "Detention Operations" OR "ICE Operations"'
            ),
            "airport": (
                'type:Dashboard "Airport Operations" OR "Airside" OR "Terminal Operations" '
                'OR "Airport Security" OR "Ramp Control" OR "Aviation Operations" '
                'OR "Airport Operations Center" OR "Airfield"'
            ),
            "port": (
                'type:Dashboard "Port Operations" OR "Maritime" OR "Harbor" '
                'OR "Seaport" OR "Vessel Tracking" OR "Port Security" '
                'OR "Marine Operations" OR "Harbor Master" OR "AIS Tracking"'
            ),

            # --- Cybersecurity ---
            "cyber": (
                'type:Dashboard "Cybersecurity" OR "SOC" OR "Security Operations Center" '
                'OR "SIEM" OR "Threat Intelligence" OR "Incident Response" '
                'OR "Cyber Threat" OR "Vulnerability" OR "Security Posture" '
                'OR "Cyber Dashboard" OR "Threat Hunt" OR "Security Monitoring"'
            ),
            # --- Environmental / hazardous ---
            "hazmat": (
                'type:Dashboard "HazMat" OR "Hazardous Materials" OR "Chemical Spill" '
                'OR "Toxic Release" OR "HAZMAT" OR "Chemical Emergency" OR "CBRN"'
            ),
            "flood": (
                'type:Dashboard "Flood" OR "Flood Control" OR "Levee" OR "Dam Operations" '
                'OR "Reservoir Operations" OR "Flood Warning" OR "Stormwater" '
                'OR "Dam Safety" OR "Spillway"'
            ),}
        self.CATEGORY_LABELS:Dict[str,str] = {
            "vms": "VMS / Surveillance",
            "its": "Transportation (ITS)",
            "ot": "Operational Technology (OT)",
            "border": "Border / Port of Entry",
            "ice": "ICE / Immigration Enforcement",
            "airport": "Airport Operations",
            "port": "Maritime / Port Operations",
            "cyber": "Cybersecurity / SOC / SIEM",
            "ics_cyber": "ICS / OT Cybersecurity",
            "hazmat": "HazMat / Chemical Emergency",
            "flood": "Flood / Dam / Levee Ops",
            "custom": "Custom Query",
            }

@dataclass
class ScanResult:
    item_id: str
    title: str
    category: str
    url: str
    status: str = "PENDING"
    owner: str = ""
    access: str = ""
    created: Optional[int] = None
    modified: Optional[int] = None
    num_views: Optional[int] = None
    type: str = "Dashboard"
    snippet: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class ArcScan:
    def __init__(self,
                 args:"argparse.namespace",
                 session:Optional[requests.Session]=None,
                 maxRes:Optional[int]=None):
        self.args = args
        self.config = ArcConfig()
        verbosity = getattr(args,"verbosity",True) 
        if verbosity == True: verbosity = False
        else: verbosity = True
        self.log = ArcLogger("ArcScan",verbosity=verbosity)
        if args.page_size != self.config.DEFAULT_PAGE_SIZE:
            self.log.pipe(f"Configured page_size to: {str(args.page_size)}") 
            self.config.DEFAULT_PAGE_SIZE = args.page_size
        if args.delay != self.config.DEFAULT_DELAY:
            self.log.pipe(f"Configured Delay to: {str(args.delay)}")
            self.config.DEFAULT_DELAY = args.delay
        if args.timeout != self.config.DEFAULT_TIMEOUT:
            self.log.pipe(f"Configured Timeout to: {str(args.timeout)}")
            self.config.DEFAULT_TIMEOUT = args.timeout
        if args.workers != self.config.DEFAULT_VERIFY_WORKERS:
            self.log.pipe(f"Configured Workers to: {str(args.workers)}")
            self.config.DEFAULT_VERIFY_WORKERS = args.workers
        self.pageSize = min(max(1,self.config.DEFAULT_PAGE_SIZE),self.config.MAX_PER_PAGE)
        self.delay = max(0.0,self.config.DEFAULT_DELAY)
        self.verifyWorkers = max(1,self.config.DEFAULT_VERIFY_WORKERS)
        self.session = session or self.buildSession()
        self._seen:Set[str] = set()
        self.maxRes = maxRes or args.max

    def buildSession(self,
                     retries:int=3,
                     backoff:float=0.4,
                     statusForceList:Sequence[int]=(429,500,502,503,504)):
        session = requests.Session()
        retry = Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=backoff,
            status_forcelist=statusForceList,
            allowed_methods=["GET","HEAD"],
            raise_on_status=False)
        adapter = HTTPAdapter(max_retries=retry,pool_connections=20,pool_maxsize=20)
        session.mount("https://",adapter)
        session.mount("http://",adapter)
        return session

    def randomHeaders(self,ua:Optional[str]=None):
        return {
            "User-Agent":str(random.choice(self.config.USERAGENTS)),
            "Accept":"application/json, text/plain, */*",
            "Accept-Language":"en-US,en;q=0.9"}

    def _get(self,
             url:str,
             params:Optional[Dict[str,Any]]=None):
        headers = self.randomHeaders()
        resp = None 
        try:
            resp = self.session.get(
                url,
                params=params,
                headers=headers,
                timeout=self.config.DEFAULT_TIMEOUT)
            if self.delay:
                time.sleep(self.delay)
        except Exception as E:
            self.log.pipe(f"Unknown exception ({str(E.__class__.__name__)}): {str(E)}",level=3)
        return resp

    def verifyItem(self,iID:str):
        url = self.config.ITEM_URL.format(item_id=iID)
        try:
            resp = self._get(url, params={"f": "json"})
            if resp.status_code != 200:
                return f"HTTP {resp.status_code}", ""
            data = resp.json()
            if "error" in data:
                return "LOCKED", ""
            access = str(data.get("access", "unknown")).lower()
            if access == "public":
                return "EXPOSED", access
            return f"RESTRICTED ({access.upper()})", access
        except requests.RequestException as E:
            self.log.pipe(f"verify_item {str(iID)} failed: ({str(E.__class__.__name__)}): {str(E)}",level=2)
            return "ERROR", ""
        except (ValueError, KeyError) as E:
            self.log.pipe(f"verify_item {str(iID)} parse error: ({str(E.__class__.__name__)}): {str(E)}",level=2)
            return "ERROR", ""

    def verifyBatch(self,results:List["ScanResult"]):
        if not results:
            return
        def _work(r:"ScanResult"):
            status,access = self.verifyItem(r.item_id)
            r.status = status
            if access:
                r.access = access
        workers = min(self.verifyWorkers,len(results))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_work, r): r for r in results}
            for fut in as_completed(futures):
                try:
                    fut.result()
                except Exception as E:
                    self.log.pipe(f"Verification worker error: ({str(E.__class__.__name__)}): {str(E)}", level=3)

    def search(self,
               q:str,
               cat:str="custom",
               start:int=1):
        params = {
            "q": q,
            "f": "json",
            "num": self.pageSize,
            "start": start,
            "sortField": "modified",
            "sortOrder": "desc",
        }
        try:
            resp = self._get(self.config.SEARCH_URL, params=params)
        except requests.RequestException as E:
            self.log.pipe(f"Search request failed: ({str(E.__class__.__name__)}): {str(E)}", level=2)
            return [], 0, -1

        if resp.status_code != 200:
            self.log.pipe(f"Search API HTTP {str(resp.status_code)}",level=2)
            return [], 0, -1
        try:
            payload = resp.json()
        except ValueError:
            self.log.pipe("Search API returned non-JSON",level=2)
            return [], 0, -1
        if "error" in payload:
            self.log.pipe(f"Search API error: {str(payload)}")
            return [], 0, -1
        total = int(payload.get("total", 0))
        nextStart = int(payload.get("nextStart", -1))
        rawRes = payload.get("results") or []
        items:List[ScanResult] = []
        for raw in rawRes:
            item_id = raw.get("id")
            if not item_id or item_id in self._seen:
                continue
            self._seen.add(item_id)
            items.append(
                ScanResult(
                    item_id=item_id,
                    title=raw.get("title") or "(untitled)",
                    category=cat,
                    url=self.config.DASHBOARD_URL.format(item_id=item_id),
                    owner=raw.get("owner") or "",
                    access=str(raw.get("access") or ""),
                    created=raw.get("created"),
                    modified=raw.get("modified"),
                    num_views=raw.get("numViews"),
                    type=raw.get("type") or "Dashboard",
                    snippet=(raw.get("snippet") or "")[:200],))
        return items, total, nextStart

    def sAll(self,
             q:str,
             cat:str="custom"):
        collected:List[ScanResult]=[]
        start = 1
        reportTotal = 0
        while True:
            page, reportTotal, nextStart = self.search(q, cat, start)
            collected.extend(page)
            self.log.pipe(f"  page start={str(start)} -> {str(len(page))} new items (running total {str(len(collected))} / reported {str(reportTotal)})",)
            if self.maxRes and len(collected) >= self.maxRes:
                collected = collected[: self.maxRes]
                break
            if nextStart <= 0 or not page:
                break
            start = nextStart
        return collected

    def buildCustomQuery(self,
                         raw:str,
                         loc:str=""):
        raw = raw.strip()
        if not raw:
            return 'type:Dashboard'
        terms = raw.split()
        if len(terms) == 1:
            q = f'type:Dashboard "{raw}"'
        else:
            phrase = f'"{raw}"'
            and_terms = " AND ".join(f'"{t}"' for t in terms if len(t) > 2)
            q = f'type:Dashboard ({phrase} OR ({and_terms}))'
        if loc.strip():
            q += f' "{loc.strip()}"'
        return q
    
    def collectActive(self):
        active: List[Tuple[str, str]] = []
        if self.args.query:
            q = self.buildCustomQuery(self.args.query, self.args.location or "")
            active.append((self.config.CATEGORY_LABELS["custom"], q))
        for key in self.config.OPERATIONAL_QUERIES:
            if getattr(self.args, key, False):
                q = self.config.OPERATIONAL_QUERIES[key]
                if self.args.location:
                    q += f' "{self.args.location.strip()}"'
                active.append((self.config.CATEGORY_LABELS[key], q))
        if self.args.all or not active:
            for key, q in self.config.OPERATIONAL_QUERIES.items():
                if self.args.location:
                    q = q + f' "{self.args.location.strip()}"'
                active.append((self.config.CATEGORY_LABELS[key], q))
        seen_q: Set[str] = set()
        unique: List[Tuple[str, str]] = []
        for label, q in active:
            if q not in seen_q:
                seen_q.add(q)
                unique.append((label, q))
        return unique

    def displayResults(self,
                      results:List[ScanResult],
                      verbose:Optional[bool] = None) -> None:
        verbose = verbose or self.args.verbosity
        if not results:
            self.log.pipe("No items found.",level=2)
            return
        self.log.pipe(f"{str(len(results))} unique assest")
        self.log.pipe(f"{str('-')*84}")
        for r in results:
            status = r.status
            msgs = [
                f"[{status}] {r.title}",
                f"\t- {str(r.url)}",
                f"\t- Owner   : {r.owner or '-'}",
                f"\t- Access  : {r.access or '-'}",
                f"\t- Category: {r.category}"]
            for m in msgs:
                self.log.pipe(f"{str(m)}")
            self.log.pipe(f"{str('-'*84)}")

    def run(self,
            queries:Sequence[Tuple[str,str]],
            verify:Optional[bool]=None):
        if verify is None:
            verify = self.args.verify
        allRes:List[ScanResult] = []
        self._seen.clear()
        for label, q_str in queries:
            self.log.pipe(f"Scanning category: {str(label)}", level=1)
            self.log.pipe(f"Query: {str(q_str)}", level=0)
            results = self.sAll(q_str, cat=label)
            self.log.pipe(f"  -> {str(len(results))} unique items")
            allRes.extend(results)
        if verify and allRes:
            self.log.pipe(f"Verifying access for {str(len(allRes))} items ({self.verifyWorkers} workers)...",)
            self.verifyBatch(allRes)
            exposed = sum(1 for r in allRes if r.status == "EXPOSED")
            self.log.pipe(f"Verification complete - {str(exposed)} EXPOSED")

        if self.args.json:
            self.exportJson(allRes,self.args.opath)
        if self.args.csv:
            self.exportCSV(allRes,self.args.opath)
        return allRes

    def _makeOutputPath(self,oPath:Optional[Path]=None):
        resolved = Path(oPath or self.args.opath)
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    def exportJson(self,results:List[Sequence[ScanResult]],path:Path):
        tPath = self._makeOutputPath(path)
        if tPath.is_dir() or not tPath.suffix:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            tFile = tPath / f"arcscan_{timestamp}.json"
        else:
            tPath.parent.mkdir(parents=True, exist_ok=True)
            tFile = tPath
        data = {
            "generated": datetime.now(timezone.utc).isoformat(),
            "source": f"ArcScan ({str(__version__)}) @ J4ck3LSyN",
            "count": len(results),
            "results": [r.to_dict() for r in results]}
        try:
            with open(tFile, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            self.log.pipe(f"Exported JSON to {str(tFile)}")
        except Exception as E:
            self.log.pipe(f"JSON export failed ({str(E.__class__.__name__)}): {str(E)}", level=3)

    def exportCSV(self,results:List[Sequence[ScanResult]],path:Path):
        tPath = self._makeOutputPath(path)
        if tPath.is_dir() or not tPath.suffix:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            tFile = tPath / f"arcscan_{timestamp}.csv"
        else:
            tPath.parent.mkdir(parents=True, exist_ok=True)
            tFile = tPath
        try:
            fieldnames = [
                "item_id", "title", "category", "url", "status",
                "owner", "access", "created", "modified",
                "num_views", "type", "snippet"]
            with open(tFile, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for r in results:
                    writer.writerow(r.to_dict())
            self.log.pipe(f"Exported CSV to {str(tFile)}")
        except Exception as E:
            self.log.pipe(f"CSV export failed ({str(E.__class__.__name__)}): {str(E)}", level=3)

def main(argv:Optional[Sequence[str]]=None):
    def argP(argv:Optional[Sequence[str]]=None):
        parser = argparse.ArgumentParser(
            prog="ArcScan.py",
            description="",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=str("\n".join([
                'Examples:',
                '  python3 %(prog)s -q "Skyline" -v',
                '  python3 %(prog)s --scada --scada-deep --ot --ics-cyber -v --json ot.json',
                '  python3 %(prog)s --ice --border --cyber -v',
                '  python3 %(prog)s --power --water --pipeline --scada -v --max 200',
                '  python3 %(prog)s -a -l "Texas" --csv texas.csv',])))
        parser.add_argument("--verbosity",action="store_true",help="")
        qgroup = parser.add_argument_group("Query selection")
        qgroup.add_argument("-q", "--query", help="Custom keyword / phrase to search")
        qgroup.add_argument("-l", "--location", default="", help="Geographic or contextual modifier")
        # Core operational
        qgroup.add_argument("--vms", action="store_true", help="Video Management / Surveillance")
        qgroup.add_argument("--its", action="store_true", help="Intelligent Transportation Systems")
        qgroup.add_argument("--ot", action="store_true", help="Operational Technology (OT) focus")
        qgroup.add_argument("--fusion", action="store_true", help="Fusion / real-time crime centers")
        qgroup.add_argument("--border", action="store_true", help="Border / port of entry")
        qgroup.add_argument("--ice", action="store_true", help="ICE / immigration enforcement")
        qgroup.add_argument("--airport", action="store_true", help="Airport operations")
        qgroup.add_argument("--port", action="store_true", help="Maritime / port operations")
        # Cybersecurity
        qgroup.add_argument("--cyber", action="store_true", help="Cybersecurity / SOC / SIEM")
        # Environmental / hazardous
        qgroup.add_argument("--flood", action="store_true", help="Flood / dam / levee ops")
        qgroup.add_argument("-a", "--all", action="store_true", help="Run all operational categories")
        # Behaviour
        bgroup = parser.add_argument_group("Behaviour")
        bgroup.add_argument("-v", "--verify", action="store_true", help="Verify live access-control status")
        bgroup.add_argument("--max", type=int, default=None, metavar="N",help="Cap total results (across all categories)")
        bgroup.add_argument("--page-size", type=int, default=50, metavar="N",help=f"Results per page (1-50, default 50)")
        bgroup.add_argument("--delay", type=float, default=0.15, metavar="SEC",help=f"Inter-request delay (default 0.15)")
        bgroup.add_argument("--timeout", type=float, default=10.0, metavar="SEC",help=f"HTTP timeout (default 10.0)")
        bgroup.add_argument("--workers", type=int, default=8, metavar="N",help=f"Concurrent verify workers (default 8)")
        # Output
        ogroup = parser.add_argument_group("Output")
        ogroup.add_argument("--opath",type=Path,default=Path(".output"),help="Output directory")
        ogroup.add_argument("--json", action="store_true",help="Write full results as JSON")
        ogroup.add_argument("--csv", action="store_true",help="Write results as CSV")
        parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
        return parser.parse_args(argv)

    args = argP(argv)
    aS = ArcScan(args=args)
    aS.log.pipe(f"ArcScan({str(__version__)}) @ J4ck3LSyN")
    queries = aS.collectActive()
    aS.log.pipe(f"Captured {str(len(queries))}/queries")
    try:
        res = aS.run(queries)
        aS.displayResults(res)
    except KeyboardInterrupt:
        aS.log.pipe("User requested termination...")
        return 130
    except Exception as E:
        aS.log.pipe(f"Unknown exception ({str(E.__class__.__name__)}): {(str(E))}")
        return 1
    exposed = sum(1 for r in res if r.status == "EXPOSED")
    restricted = sum(1 for r in res if r.status.startswith("RESTRICTED"))
    aS.log.pipe(f"Summary -> EXPOSED: {exposed} | RESTRICTED: {restricted}")
    return 0

if __name__ == "__main__": sys.exit(main())
