# -*- coding: utf-8 -*-
"""
매일 아침 & 부팅 시 자동 실행되는 모닝 뉴스 브리핑 시스템
- 제목뿐만 아니라 '기사 핵심 내용 요약'까지 함께 낭독 (PC & 스마트폰 완벽 호환)
"""
import os
import sys
import time
import json
import datetime
import urllib.request
import xml.etree.ElementTree as ET
import webbrowser
import html
import re

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_OUTPUT_PATH = os.path.join(WORKSPACE_DIR, "morning_news.html")
INDEX_OUTPUT_PATH = os.path.join(WORKSPACE_DIR, "index.html")
LOG_PATH = os.path.join(WORKSPACE_DIR, "last_run.json")

CATEGORIES_MAP = {
    "정치": ["대통령", "국회", "여야", "의원", "민주당", "국민의힘", "검찰", "법원", "재판", "시장", "총리", "장관", "법사위", "정치", "선거", "공방", "탄핵", "특검"],
    "경제": ["증시", "코스피", "코스닥", "환율", "금리", "물가", "부동산", "아파트", "청약", "은행", "수출", "무역", "관세", "기업", "실적", "주가", "상승", "하락", "반도체"],
    "IT·과학": ["AI", "인공지능", "우주", "위성", "로봇", "소프트웨어", "스마트폰", "통신", "빅테크", "카카오", "네이버", "엔비디아", "애플", "오픈AI"],
    "국제": ["미국", "중국", "일본", "러시아", "우크라이나", "트럼프", "바이든", "백악관", "유럽", "중동", "외교", "대선", "글로벌", "외신", "이스라엘", "이란"],
    "사회": ["경찰", "소방", "화재", "사고", "교통", "날씨", "병원", "의료", "복지", "사기", "수사", "지하철", "환경", "축제", "한파", "강풍", "비"]
}

CATEGORY_COLORS = {
    "정치": "#3b82f6",     # Blue
    "경제": "#10b981",     # Emerald green
    "IT·과학": "#8b5cf6",  # Violet
    "국제": "#f59e0b",     # Amber
    "사회": "#ec4899",     # Rose pink
    "종합": "#64748b"      # Slate
}

def classify_category(title, description=""):
    text = (title + " " + description).lower()
    for cat, keywords in CATEGORIES_MAP.items():
        for kw in keywords:
            if kw.lower() in text:
                return cat
    return "종합"

def clean_summary_text(raw_text):
    if not raw_text:
        return ""
    # HTML 태그 제거
    text = re.sub(r'<[^<]+?>', '', raw_text)
    text = html.unescape(text).strip()
    # 언론사 바이라인 제거 (예: (서울=연합뉴스) 홍길동 기자 = )
    text = re.sub(r'^\([가-힣\s\=\·\d\w]+\)\s*[가-힣\s\·]+\s*(기자|특파원)?\s*=\s*', '', text)
    text = re.sub(r'^\([가-힣\s\=\·\d\w]+\)\s*', '', text)
    text = re.sub(r'\[[가-힣\s]+\]\s*', '', text)
    # 사진/영상 설명 텍스트 제거
    text = re.sub(r'▲.*$', '', text)
    # 줄바꿈 및 과도한 공백 정리
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def fetch_top_news(limit=10):
    feeds = [
        ("연합뉴스", "https://www.yna.co.kr/rss/news.xml"),
        ("SBS 뉴스", "https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=01&plink=RSSREADER"),
        ("동아일보", "https://rss.donga.com/total.xml")
    ]
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    news_items = []
    
    # 제외 키워드 (단순 공지, 부고, 인사 등)
    exclude_keywords = ["[알림]", "[인사]", "[부고]", "[게시판]", "[포토]", "[카드뉴스]", "부음", "인사말", "코스피 마감", "코스닥 마감"]

    for source_name, url in feeds:
        if len(news_items) >= limit:
            break
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as response:
                content = response.read()
                try:
                    xml_str = content.decode('utf-8')
                except Exception:
                    xml_str = content.decode('euc-kr', errors='ignore')
                    
                root = ET.fromstring(xml_str)
                for item in root.findall(".//item"):
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    desc_elem = item.find("description")
                    pub_elem = item.find("pubDate")
                    
                    if title_elem is None or not title_elem.text:
                        continue
                        
                    raw_title = title_elem.text.strip()
                    raw_desc = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else ""
                    link = link_elem.text.strip() if link_elem is not None and link_elem.text else "#"
                    pub_date = pub_elem.text.strip() if pub_elem is not None and pub_elem.text else ""
                    
                    # 공지/인사 제외
                    if any(ex in raw_title for ex in exclude_keywords):
                        continue
                        
                    summary = clean_summary_text(raw_desc)
                    # 요약문이 너무 짧으면 스킵
                    if len(summary) < 25:
                        continue
                        
                    # 100~150자 내외로 깔끔하게 정리 (끝이 잘리면 마침표로 정돈)
                    if len(summary) > 160:
                        last_period = summary[:155].rfind('.')
                        if last_period > 60:
                            summary = summary[:last_period+1]
                        else:
                            summary = summary[:150] + "..."
                            
                    # 중복 방지 (유사한 제목 스킵)
                    clean_title = re.sub(r'\[.*?\]', '', raw_title).strip()
                    if any(clean_title[:10] in n["title"] for n in news_items):
                        continue
                        
                    category = classify_category(clean_title, summary)
                    
                    news_items.append({
                        "title": clean_title,
                        "summary": summary,
                        "source": source_name,
                        "link": link,
                        "category": category,
                        "color": CATEGORY_COLORS.get(category, "#64748b"),
                        "pubDate": pub_date
                    })
                    
                    if len(news_items) >= limit:
                        break
        except Exception as e:
            print(f"[{source_name}] 수집 중 에러: {e}", file=sys.stderr)
            
    return news_items

def generate_html(news_items):
    now = datetime.datetime.now()
    days_ko = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    date_str = f"{now.year}년 {now.month}월 {now.day}일 ({days_ko[now.weekday()]})"
    time_str = now.strftime("%H:%M")
    
    # TTS 스크립트: 제목 + 핵심 내용 요약문까지 풍성하게 낭독!
    tts_list = []
    for idx, item in enumerate(news_items):
        narration = f"{idx+1}번 뉴스. [{item['category']}] {item['title']}. 주요 내용입니다. {item['summary']} 보도 {item['source']}."
        tts_list.append(narration)
        
    tts_json = json.dumps(tts_list, ensure_ascii=False)
    
    cards_html = ""
    for idx, item in enumerate(news_items):
        cards_html += f"""
        <div class="news-card" data-category="{item['category']}" onclick="window.open('{item['link']}', '_blank')">
            <div class="card-left">
                <span class="news-index">{idx + 1:02d}</span>
            </div>
            <div class="card-body">
                <div class="card-meta">
                    <span class="badge" style="background-color: {item['color']}20; color: {item['color']}; border: 1px solid {item['color']}40;">
                        {item['category']}
                    </span>
                    <span class="source-tag">{item['source']}</span>
                </div>
                <h3 class="news-title">{html.escape(item['title'])}</h3>
                <p class="news-summary">{html.escape(item['summary'])}</p>
                <div class="card-footer">
                    <span class="read-more">기사 전문 읽기 →</span>
                </div>
            </div>
        </div>
        """
        
    html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <meta name="theme-color" content="#090d16">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="10대뉴스">
    <link rel="apple-touch-icon" href="https://cdn-icons-png.flaticon.com/512/3208/3208799.png">
    <link rel="manifest" href="manifest.json">
    <title>☀️ 10대 뉴스 브리핑 (본문 내용 요약 음성 지원) | {date_str}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Pretendard:wght@300;400;600;700;800&family=Outfit:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-gradient: linear-gradient(135deg, #090d16 0%, #0f172a 50%, #111827 100%);
            --card-bg: rgba(255, 255, 255, 0.04);
            --card-border: rgba(255, 255, 255, 0.08);
            --card-hover-border: rgba(99, 102, 241, 0.4);
            --card-hover-bg: rgba(255, 255, 255, 0.07);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent: #6366f1;
            --accent-glow: rgba(99, 102, 241, 0.25);
            --gold: #f59e0b;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            -webkit-tap-highlight-color: transparent;
        }}

        body {{
            font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif;
            background: var(--bg-gradient);
            color: var(--text-primary);
            min-height: 100vh;
            padding: max(20px, env(safe-area-inset-top)) 16px max(90px, calc(env(safe-area-inset-bottom) + 80px));
            display: flex;
            flex-direction: column;
            align-items: center;
        }}

        .container {{
            width: 100%;
            max-width: 840px;
        }}

        /* Header */
        header {{
            margin-bottom: 14px;
            padding: 18px 20px;
            background: rgba(15, 23, 42, 0.7);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--card-border);
            border-radius: 18px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
        }}

        .header-left {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}

        .date-badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 13px;
            font-weight: 600;
            color: var(--gold);
            letter-spacing: 0.3px;
        }}

        h1 {{
            font-family: 'Outfit', 'Pretendard', sans-serif;
            font-size: 22px;
            font-weight: 800;
            letter-spacing: -0.5px;
            background: linear-gradient(90deg, #ffffff 0%, #cbd5e1 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .header-controls {{
            display: flex;
            gap: 8px;
            align-items: center;
        }}

        .btn-refresh {{
            background: rgba(255, 255, 255, 0.08);
            color: var(--text-secondary);
            border: 1px solid var(--card-border);
            cursor: pointer;
            font-family: inherit;
            font-size: 13px;
            font-weight: 600;
            padding: 8px 14px;
            border-radius: 10px;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}

        .btn-refresh:active {{
            transform: scale(0.97);
            background: rgba(255, 255, 255, 0.15);
        }}

        /* Big Audio Hero Button */
        .big-audio-banner {{
            margin-bottom: 14px;
        }}

        .btn-big-audio {{
            width: 100%;
            padding: 16px 20px;
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
            color: #ffffff;
            border: none;
            border-radius: 16px;
            font-size: 16px;
            font-weight: 700;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            box-shadow: 0 8px 24px rgba(99, 102, 241, 0.45);
            cursor: pointer;
            transition: all 0.2s;
        }}

        .btn-big-audio:active {{
            transform: scale(0.98);
        }}

        /* Category Filter Tabs */
        .filter-tabs {{
            display: flex;
            gap: 8px;
            overflow-x: auto;
            padding-bottom: 12px;
            margin-bottom: 12px;
            scrollbar-width: none;
            -ms-overflow-style: none;
        }}
        .filter-tabs::-webkit-scrollbar {{
            display: none;
        }}
        .filter-chip {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--card-border);
            color: var(--text-secondary);
            font-size: 13px;
            font-weight: 600;
            padding: 6px 14px;
            border-radius: 20px;
            white-space: nowrap;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .filter-chip.active {{
            background: var(--accent);
            color: #ffffff;
            border-color: var(--accent);
            box-shadow: 0 2px 10px var(--accent-glow);
        }}

        /* News List */
        .news-list {{
            display: flex;
            flex-direction: column;
            gap: 14px;
        }}

        .news-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 18px 20px;
            display: flex;
            gap: 16px;
            align-items: flex-start;
            cursor: pointer;
            transition: all 0.2s ease;
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
        }}

        .news-card:active {{
            transform: scale(0.985);
            background: var(--card-hover-bg);
            border-color: var(--card-hover-border);
        }}

        .card-left {{
            display: flex;
            align-items: center;
            justify-content: center;
            min-width: 36px;
            padding-top: 2px;
        }}

        .news-index {{
            font-family: 'Outfit', sans-serif;
            font-size: 22px;
            font-weight: 800;
            color: var(--text-muted);
        }}

        .card-body {{
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}

        .card-meta {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .badge {{
            font-size: 11px;
            font-weight: 700;
            padding: 2px 7px;
            border-radius: 5px;
            letter-spacing: -0.2px;
        }}

        .source-tag {{
            font-size: 12px;
            font-weight: 500;
            color: var(--text-muted);
        }}

        .news-title {{
            font-size: 17px;
            font-weight: 700;
            line-height: 1.4;
            color: var(--text-primary);
            word-break: keep-all;
        }}

        .news-summary {{
            font-size: 14px;
            line-height: 1.55;
            color: var(--text-secondary);
            word-break: keep-all;
        }}

        .card-footer {{
            display: flex;
            justify-content: flex-end;
            margin-top: 4px;
        }}

        .read-more {{
            font-size: 11px;
            font-weight: 600;
            color: var(--accent);
        }}

        /* Floating Audio Bar (Bottom Sticky) */
        .floating-audio-bar {{
            position: fixed;
            bottom: max(16px, env(safe-area-inset-bottom));
            left: 50%;
            transform: translateX(-50%);
            width: calc(100% - 32px);
            max-width: 620px;
            background: rgba(15, 23, 42, 0.94);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(99, 102, 241, 0.4);
            border-radius: 18px;
            padding: 12px 18px;
            display: none;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            box-shadow: 0 12px 30px rgba(0, 0, 0, 0.5), 0 0 20px rgba(99, 102, 241, 0.2);
            z-index: 9999;
            animation: slideUp 0.3s ease;
        }}

        @keyframes slideUp {{
            from {{ transform: translate(-50%, 20px); opacity: 0; }}
            to {{ transform: translate(-50%, 0); opacity: 1; }}
        }}

        .audio-left {{
            display: flex;
            align-items: center;
            gap: 10px;
            flex: 1;
            overflow: hidden;
        }}

        .sound-wave {{
            display: inline-flex;
            align-items: flex-end;
            gap: 2px;
            height: 14px;
            min-width: 14px;
        }}

        .sound-wave span {{
            width: 2.5px;
            background: #818cf8;
            border-radius: 1px;
            animation: bounce 0.8s infinite alternate ease-in-out;
        }}

        .sound-wave span:nth-child(2) {{ animation-delay: 0.2s; height: 12px; }}
        .sound-wave span:nth-child(3) {{ animation-delay: 0.4s; height: 8px; }}
        .sound-wave span:nth-child(4) {{ animation-delay: 0.1s; height: 14px; }}

        @keyframes bounce {{
            0% {{ height: 3px; }}
            100% {{ height: 14px; }}
        }}

        .audio-text {{
            font-size: 13px;
            font-weight: 600;
            color: #e2e8f0;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .audio-actions {{
            display: flex;
            gap: 6px;
            align-items: center;
        }}

        .btn-ctrl {{
            background: rgba(255, 255, 255, 0.1);
            color: #fff;
            border: none;
            padding: 6px 10px;
            border-radius: 8px;
            font-size: 12px;
            cursor: pointer;
        }}

        footer {{
            margin-top: 36px;
            text-align: center;
            font-size: 12px;
            color: var(--text-muted);
            line-height: 1.6;
        }}

        @media (min-width: 641px) {{
            h1 {{ font-size: 26px; }}
            .news-card:hover {{
                background: var(--card-hover-bg);
                border-color: var(--card-hover-border);
                transform: translateX(4px);
            }}
            .news-card:hover .news-index {{ color: var(--accent); }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-left">
                <span class="date-badge">☀️ TODAY'S BRIEFING &bull; {date_str}</span>
                <h1>오늘의 핵심 뉴스 10선</h1>
            </div>
            <div class="header-controls">
                <button class="btn-refresh" onclick="location.reload()">
                    🔄 새로고침
                </button>
            </div>
        </header>

        <!-- 모바일 눈에 확 띄는 대형 음성 브리핑 배너 버튼 -->
        <div class="big-audio-banner">
            <button onclick="toggleAudio()" class="btn-big-audio" id="mainTtsBtn">
                <span id="bigTtsIcon" style="font-size: 24px;">🎧</span> 
                <span id="bigTtsText">10대 뉴스 핵심내용 음성 듣기 (터치)</span>
            </button>
        </div>

        <!-- Category Tabs -->
        <div class="filter-tabs">
            <button class="filter-chip active" onclick="filterCategory('전체', this)">전체</button>
            <button class="filter-chip" onclick="filterCategory('정치', this)">🏛️ 정치</button>
            <button class="filter-chip" onclick="filterCategory('경제', this)">📈 경제</button>
            <button class="filter-chip" onclick="filterCategory('IT·과학', this)">🤖 IT·과학</button>
            <button class="filter-chip" onclick="filterCategory('국제', this)">🌍 국제</button>
            <button class="filter-chip" onclick="filterCategory('사회', this)">🚨 사회</button>
        </div>

        <div class="news-list" id="newsList">
            {cards_html}
        </div>

        <!-- Floating Mobile Audio Bar -->
        <div class="floating-audio-bar" id="audioBar">
            <div class="audio-left">
                <div class="sound-wave">
                    <span></span><span></span><span></span><span></span>
                </div>
                <span class="audio-text" id="audioStatus">아침 뉴스 브리핑 재생 중...</span>
            </div>
            <div class="audio-actions">
                <button class="btn-ctrl" onclick="prevAudio()">⏮️</button>
                <button class="btn-ctrl" id="playPauseBtn" onclick="togglePause()">⏸️</button>
                <button class="btn-ctrl" onclick="nextAudio()">⏭️</button>
                <button class="btn-ctrl" style="background: rgba(239, 68, 68, 0.2); color: #f87171;" onclick="stopAudio()">✕</button>
            </div>
        </div>

        <footer>
            최신 업데이트: {time_str} 기준 &bull; 국가기간통신사 연합뉴스 & 주요 방송사 헤드라인<br>
            각 카드를 누르면 해당 기사 원문으로 바로 이동합니다.
        </footer>
    </div>

    <script>
        const newsItems = {tts_json};
        let synth = window.speechSynthesis;
        let isSpeaking = false;
        let isPaused = false;
        let currentIndex = 0;
        let voices = [];
        window.activeUtterance = null; // 모바일 가비지 컬렉션(GC) 방지

        function loadVoices() {{
            if (synth) {{
                voices = synth.getVoices();
            }}
        }}
        if (synth) {{
            loadVoices();
            if (synth.onvoiceschanged !== undefined) {{
                synth.onvoiceschanged = loadVoices;
            }}
        }}

        function getKoreanVoice() {{
            if (!voices.length && synth) voices = synth.getVoices();
            let ko = voices.find(v => v.lang === 'ko-KR' || v.lang === 'ko_KR');
            if (!ko) ko = voices.find(v => v.lang.startsWith('ko'));
            return ko;
        }}

        function filterCategory(cat, btn) {{
            document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            
            const cards = document.querySelectorAll('.news-card');
            cards.forEach(card => {{
                if (cat === '전체' || card.getAttribute('data-category') === cat) {{
                    card.style.display = 'flex';
                }} else {{
                    card.style.display = 'none';
                }}
            }});
        }}

        function toggleAudio() {{
            if (isSpeaking) {{
                stopAudio();
            }} else {{
                startAudio();
            }}
        }}

        function startAudio() {{
            if (!('speechSynthesis' in window)) {{
                alert("현재 브라우저는 음성 낭독 기능을 지원하지 않습니다. 삼성 인터넷 또는 Chrome 앱에서 열어주세요!");
                return;
            }}

            // 카카오톡 인앱 브라우저 안내
            const isKakao = /KAKAOTALK/i.test(navigator.userAgent);
            if (isKakao) {{
                alert("💡 카카오톡 앱 내부에서는 소리가 안 날 수 있습니다.\\n오른쪽 하단 점 3개 메뉴(⋯) ➔ [다른 브라우저로 열기]를 눌러 삼성인터넷/크롬으로 여시면 또렷하게 잘 들립니다!");
            }}

            // 모바일 오디오 슬립 해제
            synth.cancel();
            synth.resume();

            isSpeaking = true;
            isPaused = false;
            currentIndex = 0;
            document.getElementById('audioBar').style.display = 'flex';
            if (document.getElementById('bigTtsText')) {{
                document.getElementById('bigTtsText').innerText = '음성 브리핑 낭독 중지';
                document.getElementById('bigTtsIcon').innerText = '⏹️';
            }}

            setTimeout(speakNext, 80);
        }}

        function speakNext() {{
            if (!isSpeaking || currentIndex >= newsItems.length) {{
                stopAudio();
                return;
            }}

            const text = newsItems[currentIndex];
            document.getElementById('audioStatus').innerText = `[${{currentIndex + 1}}/${{newsItems.length}}] ${{text}}`;
            
            synth.cancel();
            synth.resume();

            const utter = new SpeechSynthesisUtterance(text);
            window.activeUtterance = utter; // 전역 유지

            utter.lang = 'ko-KR';
            const koVoice = getKoreanVoice();
            if (koVoice) {{
                utter.voice = koVoice;
            }}
            utter.rate = 1.0;
            utter.pitch = 1.0;

            utter.onend = function() {{
                window.activeUtterance = null;
                if (!isPaused && isSpeaking) {{
                    currentIndex++;
                    if (currentIndex < newsItems.length) {{
                        setTimeout(speakNext, 400);
                    }} else {{
                        stopAudio();
                    }}
                }}
            }};

            utter.onerror = function(e) {{
                console.error("TTS error:", e);
                window.activeUtterance = null;
                if (e.error !== 'interrupted' && e.error !== 'canceled') {{
                    document.getElementById('audioStatus').innerText = `[안내] 스마트폰 미디어 볼륨을 높여주세요.`;
                }}
            }};

            synth.speak(utter);
        }}

        function togglePause() {{
            if (!isSpeaking) return;
            if (isPaused) {{
                synth.resume();
                isPaused = false;
                document.getElementById('playPauseBtn').innerText = '⏸️';
            }} else {{
                synth.pause();
                isPaused = true;
                document.getElementById('playPauseBtn').innerText = '▶️';
            }}
        }}

        function prevAudio() {{
            if (!isSpeaking) return;
            synth.cancel();
            currentIndex = Math.max(0, currentIndex - 1);
            isPaused = false;
            document.getElementById('playPauseBtn').innerText = '⏸️';
            speakNext();
        }}

        function nextAudio() {{
            if (!isSpeaking) return;
            synth.cancel();
            currentIndex = Math.min(newsItems.length - 1, currentIndex + 1);
            isPaused = false;
            document.getElementById('playPauseBtn').innerText = '⏸️';
            speakNext();
        }}

        function stopAudio() {{
            isSpeaking = false;
            isPaused = false;
            window.activeUtterance = null;
            if (synth) {{
                synth.cancel();
            }}
            document.getElementById('audioBar').style.display = 'none';
            if (document.getElementById('bigTtsText')) {{
                document.getElementById('bigTtsText').innerText = '10대 뉴스 핵심내용 음성 듣기 (터치)';
                document.getElementById('bigTtsIcon').innerText = '🎧';
            }}
        }}
    </script>
</body>
</html>
"""
    with open(HTML_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)

    with open(INDEX_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    return HTML_OUTPUT_PATH

def main():
    force = "--force" in sys.argv
    
    if not force and os.path.exists(LOG_PATH):
        try:
            with open(LOG_PATH, "r", encoding="utf-8") as f:
                last_data = json.load(f)
                last_time = last_data.get("timestamp", 0)
                if time.time() - last_time < 900:  # 15분 이내
                    print("최근 15분 이내에 이미 브리핑이 실행되었습니다. 스킵합니다. (강제 실행: --force)")
                    if os.path.exists(HTML_OUTPUT_PATH):
                        webbrowser.open(f"file:///{HTML_OUTPUT_PATH.replace(os.sep, '/')}")
                    return
        except Exception:
            pass

    print("[1/3] 최신 주요 뉴스 10개 및 핵심 본문 요약 수집 중...")
    items = fetch_top_news(limit=10)
    if not items:
        print("뉴스 수집 실패. 기존 파일이 있는지 확인합니다.")
        return
        
    print(f"[2/3] 모닝 브리핑 대시보드 생성 중... ({len(items)}건 본문 요약 완료)")
    html_path = generate_html(items)
    
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump({"timestamp": time.time(), "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, f)
        
    if not os.environ.get("GITHUB_ACTIONS") and "--no-browser" not in sys.argv:
        print(f"[3/3] 브라우저 자동 실행: {html_path}")
        try:
            webbrowser.open(f"file:///{html_path.replace(os.sep, '/')}")
        except Exception:
            pass
    print("브리핑 완료! (index.html 본문 요약 음성 탑재 완료)")

if __name__ == "__main__":
    main()
