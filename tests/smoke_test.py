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
        rows, meds = pg.locator(".sorow").count(), pg.locator(".sorow .somed").count()
        pg.locator(".sorow .somed").first.click(); pg.wait_for_timeout(150)
        c1 = pg.inner_text(".ilb .icnt"); pg.keyboard.press("ArrowRight"); pg.wait_for_timeout(150); c2 = pg.inner_text(".ilb .icnt")
        pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
        check("단독 시스템 비교: 체크·여러 장·나란히·넘기기", sv.get("solo") is True and len(sv.get("gallery", [])) == 3 and rows == 1 and meds == 3
              and c1 == "1 / 3" and c2 == "2 / 3", f"{sv.get('solo')} {len(sv.get('gallery',[]))} {rows} {meds} {c1} {c2}")
        pg.click("[data-sooff]"); pg.wait_for_timeout(200); off = pg.locator(".sorow").count()
        pg.locator("#toast button", has_text="되돌리기").click(); pg.wait_for_timeout(300)
        check("단독 시스템 비교: 빼기·되돌리기", off == 0 and pg.locator(".sorow").count() == 1)
        pg.goto(url + "#sysref"); pg.wait_for_timeout(300)
        hidden = pg.locator(f'#rows [data-edit="{pid}"]').count() == 0
        pg.goto(url + "#sysref-tree"); pg.wait_for_timeout(300)
        check("단독 시스템은 비교 화면에서만", hidden and pg.locator('#tree [data-tnode$="\u0001패링"]:not(.ghost)').count() == 0)
        pg.goto(url + "#sysref-solo"); pg.wait_for_timeout(300); pg.click("[data-sooff]"); pg.wait_for_timeout(200)
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
        check("패치 타임라인", pg.locator(".tlbar").count() >= 1)

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
        second = pg.inner_text(".ilb .icnt") if pg.locator(".ilb .icnt").count() else ""
        check("아이디어: 크게 보기·넘기기", pg.is_visible(".ilb") and first == "1 / 2" and second == "2 / 2", f"{first}->{second}")
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
        pg.fill("#hq", "패링"); pg.wait_for_timeout(150)
        secs = pg.locator("#hres .hsec h3").all_inner_texts()
        pg.locator("#hres .hitem", has_text="강공 패링").first.click(); pg.wait_for_timeout(200)
        check("홈: 한눈에 보기·전체 검색", home_ok and any("시스템" in x for x in secs) and any("게임 정리" in x for x in secs)
              and "강공 패링" in pg.inner_text("#scrim"), str(secs))
        pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
        if pg.is_visible("#scrim"): pg.click("#gClose")

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
