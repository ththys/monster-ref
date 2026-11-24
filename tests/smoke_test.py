"""레퍼런스 아카이브 스모크 테스트 (브라우저 저장 모드)

실제 Firebase·Cloudinary 없이, config.js를 비운 '이 브라우저에만 저장' 모드로
주요 흐름을 한 번씩 눌러 봅니다. 수정할 때마다 돌리세요.

    pip install playwright && python -m playwright install chromium
    python tests/smoke_test.py            # 저장소 루트에서

성공하면 마지막 줄에 "OK"가 찍히고, 실패하면 어디서 깨졌는지 보여 줍니다.
"""
import http.server, os, shutil, socketserver, sys, tempfile, threading
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMPTY_CONFIG = 'window.REF_CONFIG = { firebase:{}, cloudinary:[], portfolio:{title:"자기소개서"}, editors:[] };\n'


def serve(dirpath):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    handler = lambda *a, **k: Quiet(*a, directory=dirpath, **k)
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def pick_or_type(pg, base, value):
    """게임·시스템 이름처럼 '드롭다운 + 직접 입력'인 칸 채우기"""
    sel = f"#{base}Sel"
    if pg.locator(sel).count() and pg.is_visible(sel):
        opts = pg.eval_on_selector_all(f"{sel} option", "os=>os.map(o=>o.value)")
        if value in opts:
            pg.select_option(sel, value); return
        pg.select_option(sel, "__new__")
    pg.fill(f"#{base}", value)


def main():
    tmp = tempfile.mkdtemp()
    shutil.copy(os.path.join(ROOT, "index.html"), tmp)
    open(os.path.join(tmp, "config.js"), "w", encoding="utf-8").write(EMPTY_CONFIG)
    httpd, port = serve(tmp)
    url = f"http://127.0.0.1:{port}/index.html"
    errors, checks = [], []

    def check(name, ok, detail=""):
        checks.append((name, ok, detail))
        print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail and not ok else ""))

    exe = "/usr/bin/google-chrome" if os.path.exists("/usr/bin/google-chrome") else None
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        pg = b.new_page(viewport={"width": 1400, "height": 900})
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.route("**/fonts.g*/**", lambda r: r.abort())
        pg.goto(url + "#monsters"); pg.wait_for_timeout(300)
        pg.evaluate("localStorage.clear()"); pg.reload(); pg.wait_for_timeout(600)

        # 1) 몬스터 추가
        pg.click("#addBtn"); pick_or_type(pg, "f_game", "테스트 게임")
        pg.fill("#f_version", "1.0"); pg.fill("#f_name", "테스트 보스"); pg.fill("#f_nameEn", "Test Boss")
        pg.fill("#f_systems", "패링"); pg.click("#fTitle"); pg.click("#fSave"); pg.wait_for_timeout(150)
        check("몬스터 추가", pg.locator("#rows td.name", has_text="테스트 보스").count() == 1)

        # 1-1) 태그는 가나다순으로 보임 (넣은 순서와 상관없이)
        pg.locator("#rows tr", has_text="테스트 보스").first.locator("[data-edit]").first.click(); pg.wait_for_timeout(100)
        pg.fill("#f_theme", "하늘 / 가시 / 바람"); pg.click("#fTitle"); pg.click("#fSave"); pg.wait_for_timeout(150)
        order = pg.evaluate("""()=>{ const r=[...document.querySelectorAll('#rows tr')].find(r=>r.textContent.includes('테스트 보스'));
            return [...r.querySelectorAll('.tag')].map(t=>t.textContent.trim()).filter(t=>['하늘','가시','바람'].includes(t)); }""")
        check("태그 가나다순", order == ["가시", "바람", "하늘"], str(order))

        # 2) 시스템 레퍼런스: 기본 시스템 (분류 있음, 부모 칸 없음)
        pg.goto(url + "#sysref"); pg.wait_for_timeout(300)
        pg.click("#addBtn")
        check("기본 시스템 창에 부모 칸 없음", pg.locator("#f_parentsSel").count() == 0 and pg.locator("#f_cats").count() == 1)
        pick_or_type(pg, "f_name", "패링"); pick_or_type(pg, "f_game", "테스트 게임")
        pg.fill("#f_cats", "전투"); pg.fill("#f_keywords", "타이밍"); pg.fill("#f_guide", "## 규칙\n타이밍 맞춰 막기")
        pg.click("#fTitle"); pg.click("#fSave"); pg.wait_for_timeout(150)

        # 3) + 확장: 확장 시스템 창 (부모·게임 채워짐, 분류 없음)
        pg.locator("#rows tr", has_text="패링").first.locator("[data-ext]").click(); pg.wait_for_timeout(100)
        check("확장 창: 부모·게임 채워짐", pg.input_value("#f_parents") == "패링" and pg.input_value("#f_game") == "테스트 게임")
        check("확장 창: 분류 없음", pg.locator("#f_cats").count() == 0)
        pick_or_type(pg, "f_name", "강공 패링"); pg.fill("#f_ext", "더 밀려남")
        pg.click("#fTitle"); pg.click("#fSave"); pg.wait_for_timeout(150)
        check("하위 시스템 기본 접힘", pg.locator("#rows td.name", has_text="강공 패링").count() == 0
              and pg.locator("[data-sgt]").count() == 1)

        # 3-1) 시스템은 고유: 같은 게임에 같은 이름이면 저장 막힘, 이름 드롭다운 없음
        pg.click("#addBtn"); pg.wait_for_timeout(100)
        no_dd = pg.locator("#f_nameSel").count() == 0
        pick_or_type(pg, "f_game", "테스트 게임"); pg.fill("#f_name", "패링"); pg.wait_for_timeout(100)
        warn = pg.is_visible("#f_nameDup")
        pg.click("#fTitle"); pg.click("#fSave"); pg.wait_for_timeout(150)
        check("시스템 이름 중복 막힘", no_dd and warn and pg.is_visible("#fErr")
              and pg.locator("#rows td.name", has_text="패링").count() == 1)
        pg.click("#fCancel"); pg.wait_for_timeout(100)

        # 3-1b) 시스템 복제: 편집 창 → 복제 → 저장하면 하나 더 생김
        pg.locator("#rows tr", has_text="패링").first.locator("[data-edit]").first.click(); pg.wait_for_timeout(100)
        pg.click("#fDup"); pg.wait_for_timeout(150)
        dup_ok = "복제" in pg.inner_text("#fTitle") and "복사본" in pg.input_value("#f_name")
        pg.click("#fSave"); pg.wait_for_timeout(200)
        check("시스템 복제", dup_ok and pg.locator("#rows td.name", has_text="패링 (복사본)").count() == 1)

        # 3-1c) 연출 변형: 움짤 + 출처 + 차이를 여러 개 기록
        png = os.path.join(tmp, "v.png")
        open(png, "wb").write(bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
            "1f15c4890000000d49444154789c6360f80f0000010101005a4d6a4f0000000049454e44ae426082"))
        pid = pg.evaluate("()=>JSON.parse(localStorage.getItem('monster-ref-v1')).find(m=>m.kind==='system'&&m.name==='패링').id")
        pg.locator(f'#rows [data-edit="{pid}"]').first.click(); pg.wait_for_timeout(100)
        pg.set_input_files("#v_files", png); pg.wait_for_timeout(400)
        pg.locator('#varEdit [data-vf="src"]').first.fill("보스 A")
        pg.locator('#varEdit [data-vf="diff"]').first.fill("성공 순간 멈춤")
        pg.click("#vText"); pg.locator('#varEdit [data-vf="diff"]').nth(1).fill("붉은 섬광")
        pg.click("#fSave"); pg.wait_for_timeout(200)
        vs = pg.evaluate("()=>(JSON.parse(localStorage.getItem('monster-ref-v1')).find(m=>m.kind==='system'&&m.name==='패링')||{}).variants||[]")
        check("연출 변형 저장", len(vs) == 2 and vs[0].get("src") == "보스 A" and bool(vs[0].get("image")) and vs[1].get("diff") == "붉은 섬광", str(vs)[:120])

        # 3-1d) 단독 시스템 비교: 체크로 넣기, 이미지 여러 장 한 번에, 나란히 보기, 크게 보고 넘기기, 빼기·되돌리기
        pg.locator(f'#rows [data-edit="{pid}"]').first.click(); pg.wait_for_timeout(100)
        pg.check("#f_solo"); pg.set_input_files("#g_files", [png, png, png]); pg.wait_for_timeout(600)
        pg.click("#fSave"); pg.wait_for_timeout(200)
        sv = pg.evaluate("()=>JSON.parse(localStorage.getItem('monster-ref-v1')).find(m=>m.kind==='system'&&m.name==='패링')")
        pg.goto(url + "#sysref-solo"); pg.wait_for_timeout(300)
        rows, meds = pg.locator(".solit").count(), pg.locator(".sothumbs button").count()
        c0 = pg.inner_text(".sopane .socnt"); pg.keyboard.press("ArrowRight"); pg.wait_for_timeout(150); c1 = pg.inner_text(".sopane .socnt")
        pg.click(".sopane .sobig"); pg.wait_for_timeout(150)
        lb1 = pg.inner_text(".ilb .icnt"); pg.keyboard.press("ArrowRight"); pg.wait_for_timeout(150); c2 = pg.inner_text(".ilb .icnt")
        pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
        check("연출 비교: 체크·여러 장·넘겨 보기·크게 보기", sv.get("solo") is True and len(sv.get("gallery", [])) == 3 and rows == 1 and meds == 3
              and c0 == "1 / 3" and c1 == "2 / 3" and lb1 == "2 / 3" and c2 == "3 / 3", f"{sv.get('solo')} {len(sv.get('gallery',[]))} {rows} {meds} {c0} {c1} {lb1} {c2}")
        pg.click(".sopane [data-sooff]"); pg.wait_for_timeout(200); off = pg.locator(".solit").count()
        pg.locator("#toast button", has_text="되돌리기").click(); pg.wait_for_timeout(300)
        check("연출 비교: 빼기·되돌리기", off == 0 and pg.locator(".solit").count() == 1)
        pg.goto(url + "#sysref"); pg.wait_for_timeout(300)
        hidden = pg.locator(f'#rows [data-edit="{pid}"]').count() == 0
        pg.goto(url + "#sysref-tree"); pg.wait_for_timeout(300)
        check("연출 비교 시스템은 거기서만", hidden and pg.locator('#tree [data-tnode$="\u0001패링"]:not(.ghost)').count() == 0)
        pg.goto(url + "#sysref-solo"); pg.wait_for_timeout(300); pg.click(".sopane [data-sooff]"); pg.wait_for_timeout(200)
        pg.goto(url + "#sysref"); pg.wait_for_timeout(300)

        # 3-2) 몬스터의 전투 확장 시스템 추천은 같은 게임의 시스템만
        pg.goto(url + "#monsters"); pg.wait_for_timeout(300)
        pg.click("#addBtn"); pick_or_type(pg, "f_game", "다른 게임")
        pg.fill("#f_systems", ""); pg.type("#f_systems", "패"); pg.wait_for_timeout(150)
        other = pg.locator(".ac:visible", has_text="패링").count()
        pick_or_type(pg, "f_game", "테스트 게임")
        pg.fill("#f_systems", ""); pg.type("#f_systems", "패"); pg.wait_for_timeout(150)
        same = pg.locator(".ac:visible", has_text="패링").count()
        check("몬스터 시스템 추천: 같은 게임만", other == 0 and same >= 1, f"other={other} same={same}")
        pg.keyboard.press("Escape"); pg.click("#fCancel"); pg.wait_for_timeout(100)

        # 4) 게임별(→분류) 보기
        pg.goto(url + "#sysref-games"); pg.wait_for_timeout(300)
        check("게임별: 게임 → 분류", pg.locator(".gsec").count() == 1 and pg.locator(".gsub").count() >= 1)
        pg.click("[data-bsg]"); pg.wait_for_timeout(100)
        check("게임별: 펼치면 하위 보임", pg.locator(".gitem.kid").count() == 1)

        # 5) 확장 구조
        pg.goto(url + "#sysref-tree"); pg.wait_for_timeout(300)
        check("확장 구조: 상자 2개·선 1개", pg.locator(".tnode").count() == 2 and pg.locator("#tree path:not(.sim)").count() == 1)
        check("확장 구조: 키워드 표시", "#타이밍" in pg.inner_text(".tree"))

        # 5-1) 우클릭 메뉴: 빈 곳 → 기본 시스템 추가, 상자 → 확장 추가
        box = pg.locator("#tree").bounding_box()
        pg.mouse.click(box["x"] + box["width"] - 10, box["y"] + box["height"] - 10, button="right"); pg.wait_for_timeout(100)
        pg.locator(".ctx button", has_text="기본 시스템 추가").click(); pg.wait_for_timeout(100)
        check("우클릭(빈 곳): 기본 시스템 창, 게임 채워짐", pg.locator("#f_cats").count() == 1 and pg.input_value("#f_game") == "테스트 게임")
        pick_or_type(pg, "f_name", "회피"); pg.click("#fTitle"); pg.click("#fSave"); pg.wait_for_timeout(200)
        pg.locator(".tnode", has_text="패링").first.click(button="right"); pg.wait_for_timeout(100)
        items = pg.locator(".ctx button").all_inner_texts()
        check("우클릭(상자): 메뉴 항목", any("확장 시스템 추가" in t for t in items) and any("삭제" in t for t in items), str(items))
        pg.keyboard.press("Escape"); pg.wait_for_timeout(100)

        # 5-2) 끌어서 부모 바꾸기 + 되돌리기 + 순환 막기
        def node(name): return pg.locator(f'[data-tnode$="\u0001{name}"]')
        def parents_of(name):
            return pg.evaluate("n=>(JSON.parse(localStorage.getItem('monster-ref-v1')||'[]').find(m=>m.kind==='system'&&m.name===n)||{}).parents||[]", name)
        node("강공 패링").drag_to(node("회피")); pg.wait_for_timeout(300)
        check("드래그: 다른 부모로 옮김", parents_of("강공 패링") == ["회피"], str(parents_of("강공 패링")))
        pg.locator("#toast button", has_text="되돌리기").click(); pg.wait_for_timeout(300)
        check("드래그: 되돌리기", parents_of("강공 패링") == ["패링"], str(parents_of("강공 패링")))
        node("패링").drag_to(node("강공 패링")); pg.wait_for_timeout(200)
        check("드래그: 자기 하위로는 막힘", parents_of("패링") == [] and "하위" in pg.inner_text("#toast"))

        # 5-3) 확장 구조에서 상자를 누르면 이미지가 보임
        pg.evaluate("""()=>{ const k='monster-ref-v1', d=JSON.parse(localStorage.getItem(k));
            d.forEach(m=>{ if(m.kind==='system'&&m.name==='패링') m.image='data:image/gif;base64,R0lGODlhAQABAAAAACw='; });
            localStorage.setItem(k, JSON.stringify(d)); }""")
        pg.reload(); pg.wait_for_timeout(500)
        node("패링").first.click(); pg.wait_for_timeout(150)
        check("확장 구조: 눌러서 이미지 보기", pg.locator(".gmedia img").count() == 1)
        pg.locator(".gmedia .gmbig").dispatch_event("click"); pg.wait_for_timeout(150)
        big = pg.is_visible(".ilb") and pg.is_visible("#scrim")
        pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
        check("설명 창: 이미지 크게 보기 → Esc는 큰 화면만 닫음", big and not pg.is_visible("#lightbox") and pg.is_visible("#scrim"))
        check("연출 변형: 설명 창·구조도 개수", pg.locator(".vcard").count() == 2 and "연출 2" in pg.inner_text("#tree"))
        pg.click("#gClose"); pg.wait_for_timeout(100)

        # 6) 몬스터 칩 → 시스템 레퍼런스 내용만 (메모 수정 없음)
        pg.goto(url + "#monsters"); pg.wait_for_timeout(300)
        pg.hover("[data-deep]"); pg.wait_for_timeout(400)
        txt = pg.inner_text("#pop")
        check("몬스터 시스템 칩 → 시스템 레퍼런스 연동", "시스템 레퍼런스" in txt and "타이밍" in txt and pg.locator("#popEdit").count() == 0, txt[:80])
        pg.mouse.move(5, 5); pg.wait_for_timeout(300)

        # 7) 패치 타임라인
        pg.goto(url + "#timeline"); pg.wait_for_timeout(300)
        if pg.locator("#tlGameSel").count(): pg.select_option("#tlGameSel", "테스트 게임"); pg.wait_for_timeout(200)
        moved = pg.evaluate("location.hash") == "#patches"
        check("패치 타임라인 (예전 주소는 게임 쪽으로)", moved and pg.locator(".tvchip.mon").count() >= 1, pg.evaluate("location.hash"))

        # 7-1) 아이디어 보드: 추가(개별 패턴) → 분류별 보기 → 끌어 놓기로 바로 추가 → 크게 보기·넘기기
        pg.goto(url + "#ideas"); pg.wait_for_timeout(300)
        check("아이디어: 빈 화면", pg.locator(".iempty").count() == 1)
        pg.click("#addBtn"); pg.wait_for_timeout(100)
        pg.check('input[name="i_type"][value="pattern"]')
        pg.set_input_files("#f_file", png); pg.wait_for_timeout(300)
        pg.fill("#f_name", "거대 실루엣"); pg.fill("#f_keywords", "웅장함")
        pg.click("#fTitle"); pg.click("#fSave"); pg.wait_for_timeout(200)
        check("아이디어: 추가", pg.locator(".icard").count() == 1 and "거대 실루엣" in pg.inner_text(".iboard") and pg.inner_text("#nIdeaP").strip() == "1")
        pg.goto(url + "#ideas-image"); pg.wait_for_timeout(200)
        check("아이디어: 분류별 보기", pg.locator(".icard").count() == 0)
        pg.evaluate("""async (b64)=>{ const bin=Uint8Array.from(atob(b64),c=>c.charCodeAt(0));
            const dt=new DataTransfer(); dt.items.add(new File([bin],"mood.png",{type:"image/png"}));
            const gb=document.getElementById("groupbox");
            gb.dispatchEvent(new DragEvent("dragover",{dataTransfer:dt,bubbles:true,cancelable:true}));
            gb.dispatchEvent(new DragEvent("drop",{dataTransfer:dt,bubbles:true,cancelable:true})); }""",
            __import__("base64").b64encode(open(png,"rb").read()).decode())
        pg.wait_for_timeout(500)
        check("아이디어: 끌어 놓기로 바로 추가", pg.locator(".icard").count() == 1 and pg.inner_text("#nIdeaI").strip() == "1")
        pg.goto(url + "#ideas"); pg.wait_for_timeout(200)
        pg.locator(".icard").first.click(); pg.wait_for_timeout(150)
        first = pg.inner_text(".ilb .icnt") if pg.locator(".ilb .icnt").count() else ""
        pg.keyboard.press("ArrowRight"); pg.wait_for_timeout(150)
        second = pg.inner_text(".ilb .icnt") if pg.locator(".ilb .icnt").count() else (pg.inner_text(".gpost .icnt") if pg.locator(".gpost .icnt").count() else "")
        if pg.locator(".gpost").count(): pg.click("#gClose"); pg.wait_for_timeout(100)
        check("아이디어: 크게 보기·넘기기", first == "1 / 2" and second == "2 / 2", f"{first}->{second}")
        pg.keyboard.press("Escape"); pg.wait_for_timeout(100)

        # 7-2) 게임 정리: 한 장에 이어 쓰는 글쓰기 (@시스템, ## 제목, 사진 커서 자리·크기, 한 번에 연결, 임시 저장)
        pg.goto(url + "#games"); pg.wait_for_timeout(300)
        pg.locator('[data-gnew="테스트 게임"]').click(); pg.wait_for_timeout(200)
        game_ok = pg.input_value("#f_game") == "테스트 게임"
        pg.fill("#f_oneLine", "패링 손맛이 좋은 게임")
        cdp = pg.context.new_cdp_session(pg)
        def ime(text):   # 한글 입력기처럼 (조합 → 확정)
            for ch in text:
                if ch.isascii(): pg.keyboard.type(ch)
                else: cdp.send("Input.imeSetComposition",{"text":ch,"selectionStart":1,"selectionEnd":1}); cdp.send("Input.insertText",{"text":ch})
            pg.keyboard.up("Shift")
        pg.click("#gwEd"); ime("@강공"); pg.wait_for_timeout(150)
        mbox = pg.locator(".mbox button").all_inner_texts()
        pg.keyboard.press("Enter"); ime("이 시원하고 패링 타이밍이 넉넉함")
        pg.keyboard.press("Enter"); ime("## 느낀 점"); pg.keyboard.press("Enter"); ime("보스가 길다")
        h2 = pg.locator("#gwEd h2").count()
        pg.click("#fLinkAll"); pg.wait_for_timeout(100)
        ed_txt = pg.inner_text("#gwEd"); o_txt = pg.input_value("#f_oneLine")
        check("게임 정리: @시스템·## 제목·한 번에 연결", game_ok and mbox == ["강공 패링"] and h2 == 1
              and "@강공 패링" in ed_txt and "@패링 타이밍" in ed_txt and o_txt.startswith("@패링"), f"{mbox} {h2} | {ed_txt[:80]} | {o_txt}")
        pg.locator("#gwEd h2").click()
        pg.set_input_files("#gwFile", png); pg.wait_for_timeout(500)
        fig_after_h2 = pg.evaluate("()=>{ const f=document.querySelector('#gwEd figure.gimg'); return !!f && f.previousElementSibling && f.previousElementSibling.tagName==='H2'; }")
        # gif·webp 파일 끌어 놓기 + 다른 사이트 그림 끌어 오기
        pg.evaluate("()=>document.querySelector('#gwEd figure.gimg').setAttribute('data-keep','1')")
        pg.evaluate("""async (b64)=>{ const bin=Uint8Array.from(atob(b64),c=>c.charCodeAt(0));
            const ed=document.getElementById("gwEd"), r=ed.querySelector("h2").getBoundingClientRect();
            const dt=new DataTransfer(); dt.items.add(new File([bin],"a.gif",{type:"image/gif"})); dt.items.add(new File([bin],"b.webp",{type:"image/webp"}));
            ed.dispatchEvent(new DragEvent("drop",{dataTransfer:dt,bubbles:true,cancelable:true,clientX:r.left+5,clientY:r.top+5}));
            const d2=new DataTransfer(); d2.setData("text/uri-list","https://example.invalid/pic.webp");
            ed.dispatchEvent(new DragEvent("drop",{dataTransfer:d2,bubbles:true,cancelable:true,clientX:r.left+5,clientY:r.top+5})); }""",
            __import__("base64").b64encode(open(png,"rb").read()).decode())
        pg.wait_for_timeout(1200)
        figs = pg.evaluate("()=>[...document.querySelectorAll('#gwEd figure.gimg')].map(f=>f.dataset.image&&f.dataset.image.startsWith('https')?'web':'file')")
        check("게임 정리: gif·webp 끌어 놓기·웹 그림", figs.count("file") == 3 and figs.count("web") == 1, str(figs))
        pg.evaluate("()=>document.querySelectorAll('#gwEd figure.gimg:not([data-keep])').forEach(x=>x.remove())")
        pg.locator("#gwEd figure.gimg .gim").click(); pg.wait_for_timeout(100)
        bar = pg.is_visible("#gwFig"); pg.click('#gwFig [data-fz="s"]')
        check("게임 정리: 사진은 커서 자리에·크기 바꾸기", fig_after_h2 and bar and pg.locator("#gwEd figure.sz-s").count() == 1)
        pg.click("#fSave"); pg.wait_for_timeout(250)
        pg.locator(".gncard[data-gnote]").first.click(); pg.wait_for_timeout(250)
        check("게임 정리: 글 보기(제목·사진·소제목)", pg.locator(".gpdoc figure.sz-s img").count() == 1 and pg.locator(".gpdoc h2").count() == 1
              and "테스트 게임" in pg.inner_text(".gpbody h1"))
        check("게임 정리: 언급한 시스템 링크", pg.locator(".gpdoc .mention").count() == 2 and pg.locator(".gpside [data-gosys]").count() == 2)
        pg.locator(".gpdoc .mention").first.hover(); pg.wait_for_timeout(200)
        check("게임 정리: 올리면 시스템 정보", pg.locator(".mcard").count() == 1 and "강공 패링" in pg.inner_text(".mcard"))
        # 임시 저장·닫기 보호
        pg.click("#gEdit"); pg.wait_for_timeout(200)
        pg.click("#gwEd"); pg.keyboard.press("Control+End"); pg.keyboard.type(" more"); pg.wait_for_timeout(4500)
        has_draft = pg.evaluate("()=>Object.keys(localStorage).some(k=>k.startsWith('monster-ref-draft:'))")
        pg.once("dialog", lambda d: d.dismiss()); pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
        still = pg.is_visible("#gwEd")
        pg.once("dialog", lambda d: d.accept()); pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
        closed = not pg.is_visible("#scrim")
        pg.locator(".gncard[data-gnote]").first.click(); pg.wait_for_timeout(150); pg.click("#gEdit"); pg.wait_for_timeout(200)
        offer = pg.is_visible("#gwDraft")
        pg.click("#gwDx"); pg.click("#fCancel"); pg.wait_for_timeout(100)
        check("게임 정리: 임시 저장·닫기 전에 묻기", has_draft and still and closed and offer, f"{has_draft} {still} {closed} {offer}")
        pg.evaluate("""()=>{ const k='monster-ref-v1', d=JSON.parse(localStorage.getItem(k));
            d.forEach(m=>{ if(m.kind==='game'){ m.guide='나중에 쓴 글: 패링 좋음'; delete m.blocks; delete m.html; } }); localStorage.setItem(k, JSON.stringify(d)); }""")
        pg.reload(); pg.wait_for_timeout(500)
        pg.locator(".gncard[data-gnote]").first.click(); pg.wait_for_timeout(150)
        pg.click("#gRelink"); pg.wait_for_timeout(300)
        check("게임 정리: 시스템 다시 연결", pg.locator(".gpdoc .mention").count() == 1)
        pg.click("#gClose"); pg.wait_for_timeout(100)

        # 7-3) 홈: 주소만 치면 홈, 숫자·최근 추가, 전체 검색 → 누르면 열림
        pg.goto(url); pg.wait_for_timeout(400)
        home_ok = pg.locator(".home").count() == 1 and pg.locator(".hstat").count() == 5 and pg.locator(".hgrid .hitem").count() >= 5
        check("홈: 이미지 저장 공간", pg.locator(".husage .hucard").count() >= 1 and "파일" in pg.inner_text(".husage"))
        pg.fill("#hq", "패링"); pg.wait_for_timeout(150)
        secs = pg.locator("#hres .hsec h3").all_inner_texts()
        pg.locator("#hres .hitem", has_text="강공 패링").first.click(); pg.wait_for_timeout(200)
        check("홈: 한눈에 보기·전체 검색", home_ok and any("시스템" in x for x in secs) and any("게임 정리" in x for x in secs)
              and "강공 패링" in pg.inner_text("#scrim"), str(secs))
        pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
        if pg.is_visible("#scrim"): pg.click("#gClose")

        # 7-4) 용어집: PC 특징을 표준 용어로 묶기 (같은 말·비슷한 말), 올리면 표준 용어, 검색·모아 보기
        pg.goto(url + "#pc"); pg.wait_for_timeout(300)
        def add_pc(game, name, traits):
            pg.click("#addBtn"); pg.wait_for_timeout(100); pick_or_type(pg, "f_game", game)
            pg.fill("#f_name", name); pg.fill("#f_traits", traits); pg.click("#fTitle"); pg.click("#fSave"); pg.wait_for_timeout(250)
        def link(term, rel="same"):
            pg.wait_for_timeout(900); pg.locator("#toast button", has_text="연결하기").click(); pg.wait_for_timeout(150)
            pg.fill("#t_name", term); pg.check(f'input[name="t_rel"][value="{rel}"]'); pg.click("#fSave"); pg.wait_for_timeout(250)
        add_pc("게임 A", "PC 하나", "명파"); link("방어 무시")
        add_pc("게임 B", "PC 둘", "관통"); link("방어 무시")
        add_pc("게임 C", "PC 셋", "방어 무시"); pg.wait_for_timeout(900)
        no_prompt = pg.locator("#toast button", has_text="연결하기").count() == 0 or not pg.is_visible("#toast")
        add_pc("게임 D", "PC 넷", "융해"); link("방어 무시", "similar")
        pg.locator('#rows [data-tword="명파"]').first.hover(); pg.wait_for_timeout(250)
        card = pg.inner_text(".mcard") if pg.locator(".mcard").count() else ""
        check("용어집: 연결·올리면 표준 용어", no_prompt and "방어 무시" in card and "관통" in card and "융해" in card, card[:120])
        pg.mouse.move(5, 5); pg.wait_for_timeout(200)
        pg.fill("#q", "방어 무시"); pg.wait_for_timeout(200)
        names = pg.locator("#rows td.name .nm").all_inner_texts()
        check("용어집: 표준 용어로 검색하면 같은 말만 모임", sorted(names) == ["PC 둘", "PC 셋", "PC 하나"], str(names))
        pg.fill("#q", ""); pg.goto(url + "#terms"); pg.wait_for_timeout(300)
        check("용어집 화면", pg.locator(".tcard").count() == 1 and "명파" in pg.inner_text(".tcard") and "3곳" in pg.inner_text(".tcard"))

        # 7-5) PC 칸: 역할·전투 방식·컨셉·특징·운용, 후킹 이미지·레벨 테마는 예전에 적은 게 있을 때만
        pg.goto(url + "#pc"); pg.wait_for_timeout(300)
        heads = pg.locator("#thead th").all_inner_texts()
        pg.click("#addBtn"); pg.wait_for_timeout(100)
        form_ok = pg.locator("#f_roles").count() == 1 and pg.locator("#f_styles").count() == 1 and pg.locator("#f_hooks").count() == 1 and pg.locator("#f_levels").count() == 0
        pick_or_type(pg, "f_game", "게임 A"); pg.fill("#f_name", "역할 PC"); pg.fill("#f_roles", "딜러"); pg.fill("#f_styles", "근접")
        pg.click("#fTitle"); pg.click("#fSave"); pg.wait_for_timeout(250)
        check("PC 칸: 핵심 이미지·역할·전투 방식·운용, 레벨 없음", form_ok and "역할" in heads and "전투 방식" in heads and "컨셉" in heads and "운용" in heads
              and "핵심 이미지" in heads and "후킹 이미지" not in heads and "레벨 테마" not in heads and pg.locator('#rows [data-tag="roles|딜러"]').count() == 1, str(heads))
        pg.evaluate("""()=>{ const k='monster-ref-v1', d=JSON.parse(localStorage.getItem(k));
            d.forEach(m=>{ if(m.kind==='pc'&&m.name==='역할 PC') m.levels=['예전 레벨']; }); localStorage.setItem(k, JSON.stringify(d)); }""")
        pg.reload(); pg.wait_for_timeout(500)
        heads2 = pg.locator("#thead th").all_inner_texts()
        pid2 = pg.evaluate("()=>JSON.parse(localStorage.getItem('monster-ref-v1')).find(m=>m.name==='역할 PC').id")
        pg.locator(f'#rows [data-edit="{pid2}"]').first.click(); pg.wait_for_timeout(150)
        lv = pg.input_value("#f_levels") if pg.locator("#f_levels").count() else ""
        pg.click("#fSave"); pg.wait_for_timeout(250)
        kept = pg.evaluate("()=>JSON.parse(localStorage.getItem('monster-ref-v1')).find(m=>m.name==='역할 PC').levels")
        check("PC 칸: 예전 레벨 테마는 남아 있음", "레벨 테마" in heads2 and lv == "예전 레벨" and kept == ["예전 레벨"], f"{heads2} {lv} {kept}")

        # 7-6) 패치 타임라인: 같은 게임의 몬스터·PC를 함께, 끄고 켜기
        pg.goto(url + "#monsters"); pg.wait_for_timeout(300)
        pg.click("#addBtn"); pick_or_type(pg, "f_game", "타임 게임"); pg.fill("#f_version", "1.0"); pg.fill("#f_name", "보스 하나"); pg.fill("#f_systems", "패링")
        pg.click("#fTitle"); pg.click("#fSave"); pg.wait_for_timeout(250)
        pg.goto(url + "#pc"); pg.wait_for_timeout(300)
        pg.click("#addBtn"); pick_or_type(pg, "f_game", "타임 게임"); pg.fill("#f_version", "1.2"); pg.fill("#f_name", "PC 하나"); pg.fill("#f_systems", "패링")
        pg.click("#fTitle"); pg.click("#fSave"); pg.wait_for_timeout(1200)
        if pg.is_visible("#toast"): pg.mouse.move(5,5)
        pg.goto(url + "#patches"); pg.wait_for_timeout(300); pg.select_option("#tlGameSel", "타임 게임"); pg.wait_for_timeout(200)
        pg.click('[data-tlview="table"]'); pg.wait_for_timeout(200)
        rows = pg.locator(".tvt tbody tr").count()
        tv = rows == 2 and pg.locator(".tvt td.k-mon .tvchip.mon").count() == 1 and pg.locator(".tvt td.k-pc .tvchip.pcm").count() == 1 and pg.locator(".tvchip.sys").count() == 1
        pg.uncheck('[data-tlshow="pc"]'); pg.wait_for_timeout(200)
        tv = tv and pg.locator(".tvt td.k-pc").count() == 0
        pg.check('[data-tlshow="pc"]'); pg.wait_for_timeout(200)
        check("패치 버전별 표: 몬스터·PC·시스템 칸 나눔, 끄고 켜기", tv, str(rows))
        pg.click('[data-tlview="bars"]'); pg.wait_for_timeout(200)
        both = pg.locator(".tlpk .tvchip.mon").count() == 1 and pg.locator(".tlpk .tvchip.pcm").count() == 1 and pg.locator(".tlpack").count() == 2 and "1.0 → 1.2" in pg.inner_text(".tlbar.c-sys")
        pg.uncheck('[data-tlshow="pc"]'); pg.wait_for_timeout(200)
        check("패치 타임라인(가로): 몬스터·PC 한 줄씩, 끄고 켜기", both and pg.locator(".tlpk .tvchip.pcm").count() == 0 and pg.locator(".tlpk .tvchip.mon").count() == 1)
        pg.check('[data-tlshow="pc"]'); pg.wait_for_timeout(100)

        # 7-6b) 타임라인 우클릭: 칸에서 PC 추가(게임·버전 채워짐), 이름표 메뉴
        pg.click('[data-tlview="bars"]'); pg.wait_for_timeout(200)
        pg.locator('.tlpack.k-pc .tlpk[data-ver="1.2"]').click(button="right"); pg.wait_for_timeout(200)
        menu = pg.inner_text(".ctx")
        pg.locator(".ctx button", has_text="PC 추가").click(); pg.wait_for_timeout(300)
        seeded = pg.input_value("#f_version") == "1.2" and "타임 게임" in pg.inner_html("#form")
        pg.fill("#f_name", "우클릭 PC"); pg.click("#fTitle"); pg.click("#fSave"); pg.wait_for_timeout(400)
        made = pg.evaluate("(JSON.parse(localStorage.getItem('monster-ref-v1'))||[]).find(m=>m.name==='우클릭 PC')||{}")
        pg.goto(url + "#patches"); pg.wait_for_timeout(300); pg.select_option("#tlGameSel", "타임 게임"); pg.wait_for_timeout(200)
        pg.locator(".tlpk .tvchip", has_text="우클릭 PC").click(button="right"); pg.wait_for_timeout(200)
        cmenu = pg.inner_text(".ctx"); pg.keyboard.press("Escape")
        check("타임라인 우클릭으로 추가·이름표 메뉴", "PC 추가" in menu and "몬스터 추가" in menu and seeded and made.get("kind") == "pc" and made.get("version") == "1.2" and made.get("game") == "타임 게임" and "편집" in cmenu and "삭제" in cmenu, f"{menu!r},{seeded},{made.get('kind')},{made.get('version')},{cmenu!r}")
        pg.click('[data-tlview="table"]'); pg.wait_for_timeout(100); pg.click('[data-tlview="bars"]'); pg.wait_for_timeout(100)

        # 7-6c) 대응 PC 도구 줄, PC 없으면 PC 줄 숨김, 패치 순서(입력 순서 + 끌어서 바꾸기)
        pg.evaluate("""()=>{ const a=JSON.parse(localStorage.getItem('monster-ref-v1'))||[]; const t=Date.now();
          a.push({id:'sk1',name:'오니교부',game:'도구 게임',version:'첫 보스',createdAt:t-3000,pcs:[{name:'폭죽',label:'',note:''}]});
          a.push({id:'sk2',name:'겐이치로',game:'도구 게임',version:'두번째',createdAt:t-2000,pcs:[{name:'폭죽',label:'',note:''},{name:'간파 베기',label:'',note:''}]});
          a.push({id:'sk3',name:'잇신',game:'도구 게임',version:'마지막',createdAt:t-1000,pcs:[{name:'간파 베기',label:'',note:''}]});
          localStorage.setItem('monster-ref-v1',JSON.stringify(a)); }""")
        pg.reload(); pg.wait_for_timeout(400); pg.goto(url + "#patches"); pg.wait_for_timeout(300); pg.select_option("#tlGameSel", "도구 게임"); pg.wait_for_timeout(200)
        order = pg.eval_on_selector_all(".tlhead .tlv", "e=>e.map(x=>x.dataset.ver)")
        tool = pg.locator(".tlbar.c-tool").count() == 2 and "첫 보스 → 두번째" in pg.inner_text(".tlbar.c-tool >> nth=0")
        nopc = pg.locator(".tlpack.k-pc").count() == 0
        pg.drag_and_drop('.tlhead .tlv[data-ver="마지막"]', '.tlhead .tlv[data-ver="첫 보스"]', target_position={"x": 5, "y": 10}); pg.wait_for_timeout(300)
        order2 = pg.eval_on_selector_all(".tlhead .tlv", "e=>e.map(x=>x.dataset.ver)")
        check("대응 PC 도구 줄·빈 PC 줄 숨김·패치 순서 끌기", order == ["첫 보스", "두번째", "마지막"] and tool and nopc and order2 == ["마지막", "첫 보스", "두번째"], f"{order},{tool},{nopc},{order2}")

        # 7-6d) 다크·라이트 전환 (새로고침 후 유지)
        before = pg.evaluate("(document.documentElement.dataset.theme||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'))==='dark'")
        pg.click("#archive [data-themebtn]"); pg.wait_for_timeout(100)
        after = pg.evaluate("document.documentElement.dataset.theme")
        pg.reload(); pg.wait_for_timeout(400)
        kept = pg.evaluate("document.documentElement.dataset.theme") == after
        pg.click("#archive [data-themebtn]"); pg.wait_for_timeout(100)
        back = (pg.evaluate("document.documentElement.dataset.theme") == "dark") == before
        check("다크·라이트 전환", after == ("light" if before else "dark") and kept and back, f"{before},{after},{kept},{back}")

        # 7-6e) 아이디어: 이미지 여러 장 + 긴 글
        img = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        pg.evaluate("""(img)=>{ const a=JSON.parse(localStorage.getItem('monster-ref-v1'))||[];
          a.push({id:'idm',kind:'idea',type:'image',name:'여러 장 아이디어',image:img,gallery:[{image:img},{image:img}],guide:'## 느낌\\n'+'붉은 하늘 아래 거대한 그림자. '.repeat(12),createdAt:Date.now()+9e9});
          localStorage.setItem('monster-ref-v1',JSON.stringify(a)); }""", img)
        pg.reload(); pg.wait_for_timeout(400); pg.goto(url + "#ideas"); pg.wait_for_timeout(400)
        card = pg.locator('.icard[data-idea="idm"]'); badge = "3" in card.locator(".ipcnt").first.inner_text()
        card.click(); pg.wait_for_timeout(300)
        wide = pg.locator(".gpost").count() == 1 and pg.locator("#gpDoc figure.gimg").count() == 2 and pg.locator("#gpDoc h3").count() == 1
        step = True
        pg.click("#gEdit"); pg.wait_for_timeout(300)
        form = pg.locator("#gwEd figure.gimg").count() == 2 and pg.locator("#gwEd h3").count() == 1 and pg.input_value("#f_name") == "여러 장 아이디어"
        pg.click("#fSave"); pg.wait_for_timeout(400)
        sv = pg.evaluate("JSON.parse(localStorage.getItem('monster-ref-v1')).find(m=>m.id==='idm')||{}")
        kept = sv.get("html", "").count("<figure") == 2 and sv.get("gallery") == [] and sv.get("kind") == "idea"
        pg.locator('.icard[data-idea="idm"]').click(); pg.wait_for_timeout(300)
        post = pg.locator(".gpost #gpDoc figure.gimg").count() == 2 and "여러 장 아이디어" in pg.inner_text(".gpost h1")
        pg.click("#gClose"); pg.wait_for_timeout(150)
        check("아이디어: 예전 여러 장 보기 → 블로그 글로 옮겨 쓰기·글 보기", badge and wide and step and form and kept and post, f"{badge},{wide},{step},{form},{kept},{post}")
        # 사진 크기 1/2 → 옆으로 나란히
        pg.locator('.icard[data-idea="idm"]').click(); pg.wait_for_timeout(300); pg.click("#gEdit"); pg.wait_for_timeout(300)
        for k in range(2):
            pg.locator("#gwEd figure.gimg .gim").nth(k).click(); pg.wait_for_timeout(100); pg.click('#gwFig [data-fz="m"]'); pg.wait_for_timeout(100)
        pg.click("#fSave"); pg.wait_for_timeout(400)
        pg.locator('.icard[data-idea="idm"]').click(); pg.wait_for_timeout(400)
        bb = [pg.locator("#gpDoc figure.gimg").nth(k).bounding_box() for k in range(2)]
        side = bb[0] and bb[1] and abs(bb[0]["y"] - bb[1]["y"]) < 3 and bb[1]["x"] > bb[0]["x"] + 50
        pg.click("#gClose"); pg.wait_for_timeout(150)
        check("글 속 사진 1/2 크기로 옆으로 나란히", side, str(bb))
        # 사진 크기 끌어서 바꾸기
        pg.locator('.icard[data-idea="idm"]').click(); pg.wait_for_timeout(300); pg.click("#gEdit"); pg.wait_for_timeout(300)
        pg.locator("#gwEd figure.gimg .gim").nth(0).click(); pg.wait_for_timeout(150)
        hb = pg.locator("#gwRs").bounding_box(); eb = pg.locator("#gwEd").bounding_box()
        pg.mouse.move(hb["x"] + 8, hb["y"] + 8); pg.mouse.down()
        target = eb["x"] + 24 + (eb["width"] - 48) * 0.30
        pg.mouse.move(target, hb["y"] + 8, steps=6); pg.mouse.up(); pg.wait_for_timeout(150)
        w = pg.evaluate("document.querySelector('#gwEd figure.gimg').getAttribute('data-w')")
        pg.click("#fSave"); pg.wait_for_timeout(400)
        hv = pg.evaluate("(JSON.parse(localStorage.getItem('monster-ref-v1')).find(m=>m.id==='idm')||{}).html||''")
        check("사진 크기 끌어서 바꾸기", w is not None and 20 <= int(w) <= 40 and f'data-w="{w}"' in hv, f"{w}")
        # 새 아이디어 글쓰기: 글 + 사진 섞어 쓰기
        pg.click("#addBtn"); pg.wait_for_timeout(300)
        nw = pg.locator("#gwEd").count() == 1 and pg.locator('input[name="i_type"]').count() == 2
        pg.fill("#f_name", "블로그 아이디어"); pg.click("#gwEd"); pg.keyboard.type("hello idea")
        pg.click("#fSave"); pg.wait_for_timeout(400)
        nv = pg.evaluate("JSON.parse(localStorage.getItem('monster-ref-v1')).find(m=>m.name==='블로그 아이디어')||{}")
        check("아이디어: 글쓰기 화면으로 새로 쓰기", nw and nv.get("kind") == "idea" and "hello idea" in nv.get("html", ""), f"{nw},{nv.get('html')}")

        # 7-7) 영상 링크: 새 탭 대신 화면 위 재생
        pg.route("**/youtube-nocookie.com/**", lambda r: r.fulfill(body="<html></html>", content_type="text/html"))
        pg.route("**/i.ytimg.com/**", lambda r: r.abort())
        pg.goto(url + "#monsters"); pg.wait_for_timeout(300)
        pg.click("#addBtn"); pick_or_type(pg, "f_game", "영상 게임"); pg.fill("#f_name", "영상 보스"); pg.fill("#f_link", "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=1m5s")
        pg.click("#fTitle"); pg.click("#fSave"); pg.wait_for_timeout(250)
        pages_before = len(pg.context.pages)
        pg.locator("#rows tr", has_text="영상 보스").locator("a.link").click(); pg.wait_for_timeout(300)
        src = pg.get_attribute("#lightbox iframe", "src") or ""
        check("영상 링크: 화면 위에서 재생", pg.is_visible("#lightbox .vplay") and "dQw4w9WgXcQ" in src and "start=65" in src and len(pg.context.pages) == pages_before, src)
        pg.keyboard.press("Escape"); pg.wait_for_timeout(100)

        # 7-9) 불러오기: 이미 있는 항목(이름·영문·_alt)은 건너뜀
        import json as _j, tempfile as _t, os as _o
        jf = _o.path.join(_t.mkdtemp(), "imp.json")
        open(jf, "w", encoding="utf8").write(_j.dumps({"monsters": [
            {"kind": "pc", "game": "가져온게임", "version": "1.0", "name": "가져온 PC", "nameEn": "Imported PC"},
            {"kind": "pc", "game": "가져온게임", "version": "1.1", "name": "다른 이름", "nameEn": "Other", "_alt": ["가져온 PC"]},
            {"game": "가져온게임", "version": "1.0", "name": "Imported Mon", "nameEn": "Imported Mon"}]}, ensure_ascii=False))
        cnt = lambda: pg.evaluate("JSON.parse(localStorage.getItem('monster-ref-v1')||'[]').filter(m=>m.game==='가져온게임').length")
        pg.set_input_files("#importFile", jf); pg.wait_for_timeout(500); n1 = cnt()
        pg.set_input_files("#importFile", jf); pg.wait_for_timeout(500); n2 = cnt()
        has_alt = pg.evaluate("JSON.parse(localStorage.getItem('monster-ref-v1')||'[]').some(m=>'_alt' in m)")
        jf2 = _o.path.join(_t.mkdtemp(), "imp2.json")
        open(jf2, "w", encoding="utf8").write(_j.dumps({"monsters": [{"kind": "pc", "game": "외형게임", "name": "외형 PC", "theme": ["기사"], "looks": ["갑옷"]}]}, ensure_ascii=False))
        pg.set_input_files("#importFile", jf2); pg.wait_for_timeout(500)
        pg.goto(url + "#pc"); pg.wait_for_timeout(300)
        heads = pg.inner_text("#thead"); row = pg.locator("#rows tr", has_text="외형 PC")
        merged = row.locator(".tag", has_text="갑옷").count() == 1 and row.locator(".tag", has_text="기사").count() == 1
        row.locator("button", has_text="편집").click(); pg.wait_for_timeout(300)
        noField = pg.locator("#f_looks").count() == 0 and "갑옷" in pg.input_value("#f_theme")
        pg.click("#fSave"); pg.wait_for_timeout(300)
        saved = pg.evaluate("(JSON.parse(localStorage.getItem('monster-ref-v1')||'[]').find(m=>m.name==='외형 PC')||{})")
        check("PC 외형 칸 없음·예전 외형은 컨셉으로", "외형" not in heads and merged and noField and "갑옷" in saved.get("theme", []) and not saved.get("looks"), f"{merged},{noField},{saved.get('theme')}")
        check("불러오기: 겹치는 항목 건너뜀", n1 == 2 and n2 == 2 and not has_alt, f"{n1},{n2},{has_alt}")

        # 7-10) 편집 창 안에서 누르고 바깥에서 놓아도 안 닫힘
        pg.goto(url + "#monsters"); pg.wait_for_timeout(300)
        pg.click("#addBtn"); pg.wait_for_timeout(200)
        bx = pg.locator("#f_name").bounding_box()
        pg.mouse.move(bx["x"] + 5, bx["y"] + 5); pg.mouse.down(); pg.mouse.move(3, 3, steps=4); pg.mouse.up(); pg.wait_for_timeout(200)
        still = pg.is_visible("#f_name")
        pg.mouse.click(3, 3); pg.wait_for_timeout(200)
        closed_or_asked = not pg.is_visible("#f_name") or pg.locator("#scrim").is_visible()
        check("바깥에서 마우스를 놓아도 편집 창 유지", still, str(still))
        if pg.is_visible("#f_name"): pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
        if pg.is_visible("#f_name"): pg.evaluate("document.querySelector('#scrim').hidden=true")

        # 7-11) 휴지통: 지우면 보관, 되살리기, 완전히 삭제
        pg.goto(url + "#monsters"); pg.wait_for_timeout(300)
        pg.click("#addBtn"); pick_or_type(pg, "f_game", "휴지통 게임"); pg.fill("#f_name", "지울 보스"); pg.click("#fTitle"); pg.click("#fSave"); pg.wait_for_timeout(300)
        pg.locator("#rows tr", has_text="지울 보스").locator("[data-del]").click(); pg.wait_for_timeout(200); pg.click("#dYes"); pg.wait_for_timeout(300)
        gone = pg.locator("#rows tr", has_text="지울 보스").count() == 0
        kept = pg.evaluate("JSON.parse(localStorage.getItem('monster-ref-v1')).some(m=>m.name==='지울 보스'&&m.deletedAt)")
        pg.goto(url + "#trash"); pg.wait_for_timeout(300)
        inbin = pg.locator(".binitem", has_text="지울 보스").count() == 1 and "28일 남음" in pg.inner_text(".binitem")
        pg.locator(".binitem", has_text="지울 보스").locator("[data-trback]").click(); pg.wait_for_timeout(300)
        pg.goto(url + "#monsters"); pg.wait_for_timeout(300)
        back = pg.locator("#rows tr", has_text="지울 보스").count() == 1
        pg.locator("#rows tr", has_text="지울 보스").locator("[data-del]").click(); pg.wait_for_timeout(200); pg.click("#dYes"); pg.wait_for_timeout(300)
        pg.goto(url + "#trash"); pg.wait_for_timeout(300)
        pg.once("dialog", lambda d: d.accept())
        pg.locator(".binitem", has_text="지울 보스").locator("[data-trkill]").click(); pg.wait_for_timeout(300)
        purged = not pg.evaluate("JSON.parse(localStorage.getItem('monster-ref-v1')).some(m=>m.name==='지울 보스')")
        old = pg.evaluate("""()=>{ const a=JSON.parse(localStorage.getItem('monster-ref-v1')); a.push({id:'old1',name:'오래된 것',game:'x',deletedAt:Date.now()-29*864e5}); localStorage.setItem('monster-ref-v1',JSON.stringify(a)); }""")
        pg.reload(); pg.wait_for_timeout(500)
        autodel = not pg.evaluate("JSON.parse(localStorage.getItem('monster-ref-v1')).some(m=>m.id==='old1')")
        check("휴지통: 보관·되살리기·완전 삭제·4주 지나면 자동 삭제", gone and kept and inbin and back and purged and autodel, f"{gone},{kept},{inbin},{back},{purged},{autodel}")

        # 8) 새로고침 후 유지
        pg.reload(); pg.wait_for_timeout(500); pg.goto(url + "#monsters"); pg.wait_for_timeout(300)
        check("새로고침 후 데이터 유지", pg.locator("#rows td.name", has_text="테스트 보스").count() == 1)

        # 8-1) 왼쪽 메뉴: 기본은 접힘, 지금 보는 화면 묶음만 펼침, 눌러서 펼치기
        pg.evaluate("localStorage.removeItem('monster-ref-nav-open')"); pg.goto(url + "#monsters"); pg.reload(); pg.wait_for_timeout(400)
        hid = pg.evaluate("()=>['mon','pc','sys','game','idea'].map(k=>document.getElementById('navg-'+k).hidden)")
        pg.click('.navtog[data-grp="sys"]'); pg.wait_for_timeout(100)
        check("메뉴 기본 접힘·눌러서 펼치기", hid == [False, True, True, True, True] and pg.is_visible('a[data-view="sysref-tree"]'), str(hid))

        # 9) 폰 너비에서 가로 넘침 없음
        pg.set_viewport_size({"width": 390, "height": 800}); pg.wait_for_timeout(200)
        check("폰 너비 가로 넘침 없음", not pg.evaluate("document.documentElement.scrollWidth>innerWidth"))
        b.close()
    httpd.shutdown()

    check("페이지 스크립트 오류 없음", not errors, "; ".join(errors[:3]))
    failed = [c for c in checks if not c[1]]
    print("OK" if not failed else f"FAILED {len(failed)}/{len(checks)}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
