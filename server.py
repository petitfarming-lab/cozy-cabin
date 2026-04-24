import json
import re
import urllib.request
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler

NAVER_CLIENT_ID     = "XnaCA4YTsytR8MTKOqMX"
NAVER_CLIENT_SECRET = "5Fsct_pbdj"
KAKAO_REST_KEY      = "7add52a8e4012a5cca13d4ea56c93078"

STAY_RE = re.compile(
    r'[가-힣a-zA-Z0-9_·\-]{1,15}'
    r'(?:펜션|하우스|스테이|빌라|글램핑|독채|게스트하우스|풀빌라|카라반|민박|로지|inn|villa|stay|house|farm)',
    re.IGNORECASE
)
HTML_TAG_RE = re.compile(r'<[^>]+>')


def naver_blog_search(query, display=30):
    params = urllib.parse.urlencode({"query": query, "display": display, "sort": "sim"})
    url = f"https://openapi.naver.com/v1/search/blog.json?{params}"
    req = urllib.request.Request(url, headers={
        "X-Naver-Client-Id":     NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    })
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def extract_stay_names(items):
    names = []
    seen = set()
    for item in items:
        text = HTML_TAG_RE.sub("", item.get("title", "") + " " + item.get("description", ""))
        for m in STAY_RE.findall(text):
            key = m.strip()
            if key not in seen and len(key) >= 3:
                seen.add(key)
                names.append(key)
    return names


def kakao_geocode(name, location):
    params = urllib.parse.urlencode({"query": f"{location} {name}", "size": 1})
    url = f"https://dapi.kakao.com/v2/local/search/keyword.json?{params}"
    req = urllib.request.Request(url, headers={"Authorization": f"KakaoAK {KAKAO_REST_KEY}"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        docs = data.get("documents", [])
        if docs:
            return {
                "name":     docs[0]["place_name"],
                "address":  docs[0].get("road_address_name") or docs[0].get("address_name", ""),
                "url":      docs[0].get("place_url", ""),
                "lat":      float(docs[0]["y"]),
                "lng":      float(docs[0]["x"]),
            }
    except Exception:
        pass
    return None


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/search":
            qs = urllib.parse.parse_qs(parsed.query)
            location = qs.get("q", [""])[0].strip()
            if location:
                self.handle_search(location)
            else:
                self.send_json({"places": [], "blogs": []})
        else:
            super().do_GET()

    def handle_search(self, location):
        try:
            blog_data = naver_blog_search(f"{location} 감성숙소")
            items = blog_data.get("items", [])
            names = extract_stay_names(items)
            places = []
            seen_names = set()
            for name in names[:20]:
                result = kakao_geocode(name, location)
                if result and result["name"] not in seen_names:
                    seen_names.add(result["name"])
                    places.append(result)
            blogs = [
                {
                    "title":   HTML_TAG_RE.sub("", item["title"]),
                    "link":    item["link"],
                    "blogger": item.get("bloggername", ""),
                }
                for item in items[:5]
            ]
            self.send_json({"places": places, "blogs": blogs})
        except Exception as e:
            self.send_json({"places": [], "blogs": [], "error": str(e)})

    def send_json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8888))
    print(f"서버 시작: http://localhost:{port}")
    HTTPServer(("", port), Handler).serve_forever()
