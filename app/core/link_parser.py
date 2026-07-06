"""网页超链接解析工具。

自动提取文本中的 URL 地址，抓取对应的网页标题、描述、图标以及封面图信息。
限制单次请求超时为 2.0s 且支持非阻塞容错。使用 httpx 替代 requests。
"""

from __future__ import annotations

import re
from urllib.parse import urlparse
import httpx

# 正则匹配文本中的 HTTP/HTTPS 链接
URL_PATTERN = re.compile(
    r'(https?://[a-zA-Z0-9.\-_]+(?::\d+)?(?:/[^\s]*)?)'
)


def extract_urls(text: str) -> list[str]:
    """从文本中提取出所有的 URL。"""
    if not text:
        return []
    urls = URL_PATTERN.findall(text)
    seen = set()
    result = []
    for u in urls:
        clean_u = u.rstrip(".,;!?)']\"")
        if clean_u not in seen:
            seen.add(clean_u)
            result.append(clean_u)
    return result


def parse_url_metadata(url: str) -> dict:
    """抓取单个 URL 网页的元数据。"""
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path

    default_result = {
        "url": url,
        "title": domain,
        "description": "暂无描述",
        "favicon": f"{parsed.scheme}://{domain}/favicon.ico" if parsed.scheme else "",
        "image": "",
    }

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        }
        # 使用 httpx.Client 进行安全重定向获取
        with httpx.Client(follow_redirects=True, timeout=2.0) as client:
            resp = client.get(url, headers=headers)
        
        if resp.status_code != 200:
            return default_result

        # 如果响应不是文本，则跳过
        content_type = resp.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            return default_result

        # 尝试解码网页文本
        html = resp.text

        # 1. 提取网页标题
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else domain

        # 2. 提取 Meta 标签中的 Description
        description = "暂无描述"
        desc_match = re.search(
            r"<meta[^>]+(?:name|property)=[\"'](?:description|og:description)[\"'][^>]+content=[\"'](.*?)[\"']",
            html,
            re.IGNORECASE | re.DOTALL,
        )
        if not desc_match:
            desc_match = re.search(
                r"<meta[^>]+content=[\"'](.*?)[\"'][^>]+(?:name|property)=[\"'](?:description|og:description)[\"']",
                html,
                re.IGNORECASE | re.DOTALL,
            )
        if desc_match:
            description = desc_match.group(1).strip()

        # 3. 提取 OpenGraph 图片 (OG Image) 或封面图
        image = ""
        img_match = re.search(
            r"<meta[^>]+(?:name|property)=[\"'](?:og:image|twitter:image)[\"'][^>]+content=[\"'](.*?)[\"']",
            html,
            re.IGNORECASE | re.DOTALL,
        )
        if not img_match:
            img_match = re.search(
                r"<meta[^>]+content=[\"'](.*?)[\"'][^>]+(?:name|property)=[\"'](?:og:image|twitter:image)[\"']",
                html,
                re.IGNORECASE | re.DOTALL,
            )
        if img_match:
            image = img_match.group(1).strip()
            # 如果是相对路径，拼成绝对路径
            if image.startswith("//"):
                image = f"{parsed.scheme or 'http'}:{image}"
            elif image.startswith("/") and parsed.scheme and domain:
                image = f"{parsed.scheme}://{domain}{image}"

        # 4. 提取 Favicon
        favicon = default_result["favicon"]
        fav_match = re.search(
            r"<link[^>]+rel=[\"'](?:shortcut )?icon[\"'][^>]+href=[\"'](.*?)[\"']",
            html,
            re.IGNORECASE | re.DOTALL,
        )
        if not fav_match:
            fav_match = re.search(
                r"<link[^>]+href=[\"'](.*?)[\"'][^>]+rel=[\"'](?:shortcut )?icon[\"']",
                html,
                re.IGNORECASE | re.DOTALL,
            )
        if fav_match:
            fav_href = fav_match.group(1).strip()
            if fav_href.startswith("//"):
                favicon = f"{parsed.scheme or 'http'}:{fav_href}"
            elif fav_href.startswith("/") and parsed.scheme and domain:
                favicon = f"{parsed.scheme}://{domain}{fav_href}"
            elif fav_href.startswith("http"):
                favicon = fav_href

        return {
            "url": url,
            "title": title[:128],
            "description": description[:300],
            "favicon": favicon,
            "image": image,
        }

    except Exception:
        # 网络异常或超时，直接返回默认备用数据
        return default_result


def parse_links_in_text(text: str) -> list[dict]:
    """提取文本中的所有链接并解析生成预览卡片数据。"""
    urls = extract_urls(text)
    return [parse_url_metadata(u) for u in urls]
