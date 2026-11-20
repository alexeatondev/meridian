"""UAT-TRD-30/31 (trade files viewer, trades in progress) and POL-1..4 (Policy screen), 2026-11-18."""
from playwright.sync_api import expect

from conftest import trade_create, trade_preview, trade_setup, trading_tab

R = "UAT: browser test reason"


def _toast(page, text):
    expect(page.locator("#mtoasts")).to_contain_text(text, timeout=8000)


def _approve_and_export(page):
    page.check("#taChk")
    page.fill("#taReason", R)
    page.click("#taGo")
    _toast(page, "approved")
    with page.expect_download() as dl:
        page.click("#taCrd")
    return open(dl.value.path()).read()


def test_trd_30_31_files_and_in_progress(sign_in, app_url):
    """TRD-30: the exported Charles River file is kept and opens in the app. TRD-31: In progress shows the list."""
    page = sign_in("Maya Chen", "portfolio_manager", "approver")
    page.goto(app_url + "/trading")
    trading_tab(page, "Cashflows")
    page.select_option("#cfFund", "MTRT-2035")
    page.fill("#cfAmt", "4000000")
    page.click("#cfAdd")
    _toast(page, "Cashflow added")
    page.click("#veh button:text-is('CITs')")
    trade_setup(page, "invest", strat="neutral")
    trade_preview(page)
    trade_create(page, R)
    tl = page.locator("#tlDetail h2").first.inner_text().split()[0]
    # a draft is waiting for approval
    trading_tab(page, "In progress")
    expect(page.locator("#progress .stage").first).to_contain_text(tl)
    page.click(f"#progress [data-gotl='{tl}']")
    expect(page.locator(".tabs button.active")).to_have_text("Trade lists")
    sent = _approve_and_export(page)
    # the Charles River card links to the stored file
    page.click("#tlDetail [data-openfile]")
    expect(page.locator(".tabs button.active")).to_have_text("Files")
    fv = page.locator("#fileView")
    expect(fv).to_contain_text(f"charles-river-import-{tl}-1.csv")
    expect(fv.locator("th").first).to_have_text("External Order ID")
    assert fv.locator("tr").count() == len(sent.strip().splitlines())       # header + every row, as sent
    expect(page.locator("#files")).to_contain_text("Charles River import")
    # the list is now with Charles River; its orders are on the blotter
    trading_tab(page, "In progress")
    expect(page.locator("#progress .stage").nth(2)).to_contain_text(tl)
    page.fill("#pq", tl)
    expect(page.locator("#progress table").nth(1)).to_contain_text("MTRT-2035")
    page.click("#veh button:text-is('All funds')")


def test_pol_01_ips_change_needs_ic_and_cco(sign_in, app_url):
    """POL-1/2: a PM proposes an IPS change; IC approves, then the CCO; the redline shows the change."""
    page = sign_in("Maya Chen", "portfolio_manager")
    page.goto(app_url + "/policy")
    expect(page.locator("#ips")).to_contain_text("Version 1")
    page.click("#ipsNew")
    txt = page.locator("#ipsText")
    txt.fill(txt.input_value().replace("At least annually", "At least twice a year", 1))
    page.fill("#ipsSum", "Review the IPS twice a year")
    page.check("input[name=rc][value=no]")
    page.click("#ipsPrev")
    expect(page.locator("#ipsRl")).to_contain_text("1 changed line against")
    page.click("#ipsGo")
    _toast(page, "submitted for approval")
    expect(page.locator("#ips .rl ins")).to_contain_text("twice")
    expect(page.locator("#ips")).to_contain_text("Waiting for an Investment Committee member and the CCO")
    page = sign_in("Elena Rossi", "leadership", "investment_committee")
    page.goto(app_url + "/policy")
    page.click("[data-dec=approve][data-as=ic]")
    page.fill("dialog textarea", R)
    page.click("dialog [value=ok]")
    _toast(page, "1 of 2 approvals")
    page = sign_in("Robert Hayes", "compliance", "chief_compliance_officer")
    page.goto(app_url + "/policy")
    page.click("[data-dec=approve][data-as=cco]")
    page.fill("dialog textarea", R)
    page.click("dialog [value=ok]")
    _toast(page, "now current")
    expect(page.locator("#ips .ver").first).to_contain_text("Current")
    expect(page.locator("#ips .ver").nth(1)).to_contain_text("Superseded")


def test_pol_03_named_glide_path_assigned_to_a_fund(sign_in, app_url):
    """POL-3/4: a PM proposes a named path; IC approves; a fund is moved to it after a second IC approval."""
    page = sign_in("Maya Chen", "portfolio_manager")
    page.goto(app_url + "/policy")
    page.click(".tabs button:text-is('Glide paths')")
    page.click("#gpNew")
    page.click("#wExpert")                                             # skip the guided builder
    page.fill("#gpName", "Higher equity at retirement")
    # +2pp US large cap, -2pp core bond at the 0-year anchor (row 6)
    lc, core = page.locator("[data-r='5'][data-c='1']"), page.locator("[data-r='5'][data-c='7']")
    lc.fill(str(float(lc.input_value()) + 2))
    core.fill(str(float(core.input_value()) - 2))
    expect(page.locator("#tot5")).to_have_text("100.0")
    page.click("#gpGo")
    page.fill("dialog textarea", R)
    page.click("dialog [value=ok]")
    _toast(page, "sent to the Investment Committee")
    expect(page.locator("#paths")).to_contain_text("Waiting for the Investment Committee")
    assert page.locator("[data-gpd=approve]").count() == 0           # can't approve your own request
    page = sign_in("Elena Rossi", "leadership", "investment_committee")
    page.goto(app_url + "/policy")
    page.click(".tabs button:text-is('Glide paths')")
    page.click("[data-gpd=approve]")
    page.fill("dialog textarea", R)
    page.click("dialog [value=ok]")
    _toast(page, "approved")
    row = page.locator("[data-path]", has_text="Higher equity at retirement")
    expect(row).to_contain_text("Active")
    page = sign_in("Maya Chen", "portfolio_manager")
    page.goto(app_url + "/policy")
    page.click(".tabs button:text-is('Glide paths')")
    page.check("[data-fsel='MTRS-2030']")
    page.select_option("#gpTo", label="Higher equity at retirement")
    page.click("#gpAssign")
    page.fill("dialog textarea", R)
    page.click("dialog [value=ok]")
    _toast(page, "sent to the Investment Committee")
    page = sign_in("Elena Rossi", "leadership", "investment_committee")
    page.goto(app_url + "/policy")
    page.click(".tabs button:text-is('Glide paths')")
    page.click("[data-gpd=approve]")
    page.fill("dialog textarea", R)
    page.click("dialog [value=ok]")
    _toast(page, "approved")
    expect(page.locator("tr", has=page.locator("td.mono", has_text="MTRS-2030"))).to_contain_text("Higher equity at retirement")
    page.click(".tabs button:text-is('Change log')")
    expect(page.locator("#log")).to_contain_text("glide-path.approve")


def test_pol_07_guided_glide_path_builder(sign_in, app_url):
    """POL-7: Console → Glide path → + New glide path walks a PM through building a path from scratch."""
    page = sign_in("Maya Chen", "portfolio_manager")
    page.click("#nav button:text-is('Glide path')")
    page.click("#gpNewPath")
    expect(page.locator(".wsteps li.on")).to_contain_text("Name it")
    page.click("#wNext")
    _toast(page, "at least 3 characters")
    page.fill("#wName", "IPS glide path")
    page.click("#wNext")
    _toast(page, "already exists")
    page.fill("#wName", "Through retirement 55")
    page.fill("#wDesc", "Holds 55% equity at the target date")
    page.click("#wNext")
    expect(page.locator(".wsteps li.on")).to_contain_text("Starting point")
    page.click("#wNext")                                               # from scratch (default)
    expect(page.locator(".wsteps li.on")).to_contain_text("Shape the equity path")
    page.fill("#shFlat", "50")
    page.click("#wNext")
    _toast(page, "Start reducing")
    page.fill("#shFlat", "25")
    page.fill("#shEqTarget", "55")
    page.fill("#shEqEnd", "35")
    page.click("#wNext")
    expect(page.locator(".wsteps li.on")).to_contain_text("Fine-tune the mix")
    rows = page.locator("table.anch tr")
    expect(rows).to_have_count(9)                                      # header + 40, 25, 20, 15, 10, 5, 0, -7
    for i in range(8):
        expect(page.locator(f"#wt{i}")).to_have_text("100.0")
    page.locator("[data-wr='0'][data-wc='1']").fill("60")             # break a row
    page.click("#wNext")
    expect(page.locator(".warnbox")).to_contain_text("Fix these first")
    page.click("#wNext")
    _toast(page, "Fix the items in red")
    page.click("#wBack")
    page.locator("[data-wr='0'][data-wc='1']").fill(page.locator("[data-wr='0'][data-wc='1']").get_attribute("value"))
    page.click("#wBack"); page.click("#wNext")                         # rebuild from the shape
    page.click("#wNext")
    expect(page.locator("#paths")).to_contain_text("40 yrs: 90.")
    page.fill("#wReason", "UAT: path holding 55% equity at the target date")
    page.click("#wNext")
    _toast(page, "sent to the Investment Committee")
    expect(page.locator("#paths")).to_contain_text("Through retirement 55")
    expect(page.locator("#paths")).to_contain_text("Waiting for the Investment Committee")
