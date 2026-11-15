"""Optional browser smoke test. Requires Playwright and installed Microsoft Edge.

Run against a local seeded demo server. The script only reads app data; it does
not submit reports or alter machine / ticket records.
"""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get('VOMANTIS_TEST_URL', 'http://127.0.0.1:8000')
PASSWORD = os.environ.get('VOMANTIS_DEMO_PASSWORD', 'DemoMaint!2026')


def main():
    output = ROOT / 'artifacts'
    output.mkdir(exist_ok=True)
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='msedge', headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 1050}, device_scale_factor=1)
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('response', lambda response: errors.append(f'HTTP {response.status} {response.url}') if response.status >= 400 else None)
        page.goto(BASE_URL + '/login/')
        page.get_by_label('Username', exact=True).fill('manager')
        page.get_by_label('Password', exact=True).fill(PASSWORD)
        page.get_by_role('button', name='Masuk ke workspace').click()
        page.wait_for_url(BASE_URL + '/')
        page.get_by_role('heading', name='Operasional dalam kendali.').wait_for()
        page.screenshot(path=str(output / 'browser-dashboard-desktop.png'), full_page=True)
        for route in ['/machines/', '/tickets/', '/schedule/', '/analytics/', '/data/', '/tickets/WO-DEMO-0005/']:
            page.goto(BASE_URL + route)
            assert page.locator('h1').count() == 1, route
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Horizontal page overflow: {route}'
        page.goto(BASE_URL + '/machines/VM-DEMO-0001/')
        page.locator('img.qr-code').wait_for()
        page.wait_for_function('document.querySelector("img.qr-code").naturalWidth > 0')
        page.goto(BASE_URL + '/tickets/new/')
        page.get_by_role('button', name='Simpan perubahan').click()
        assert page.locator(':invalid').count() > 0, 'Required fields must block empty submission'
        context.close()

        context = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=1)
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(BASE_URL + '/login/')
        page.get_by_label('Username', exact=True).fill('teknisi')
        page.get_by_label('Password', exact=True).fill(PASSWORD)
        page.get_by_role('button', name='Masuk ke workspace').click()
        page.wait_for_url(BASE_URL + '/')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile dashboard overflows'
        page.screenshot(path=str(output / 'browser-dashboard-mobile.png'), full_page=True)
        page.get_by_role('button', name='Buka menu').click()
        assert page.get_by_role('button', name='Buka menu').get_attribute('aria-expanded') == 'true'
        page.locator('.app-nav').get_by_role('link', name='Work order').click()
        page.wait_for_url(BASE_URL + '/tickets/')
        assert page.get_by_role('heading', name='Work order saya').is_visible()
        page.goto(BASE_URL + '/tickets/WO-DEMO-0003/report/')
        assert page.locator('select').evaluate('(e) => getComputedStyle(e).color') == 'rgb(237, 240, 247)', 'Select text must remain readable on the dark template'
        page.get_by_role('button', name='+ Tambah kartu').click()
        assert page.locator('#id_cards-TOTAL_FORMS').input_value() == '2'
        assert page.locator('#id_cards-1-komponen').is_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile report overflows'
        page.screenshot(path=str(output / 'browser-report-mobile.png'), full_page=True)
        page.once('dialog', lambda dialog: dialog.accept())
        page.get_by_role('button', name='Hapus kartu kosong terakhir').click()
        assert page.locator('#id_cards-TOTAL_FORMS').input_value() == '1'
        context.close()
        browser.close()
    if errors:
        raise AssertionError('\n'.join(errors))
    print('OK: desktop + mobile login, dashboard, navigation, pages, QR, required fields, dynamic action cards, no JS/HTTP errors.')


if __name__ == '__main__':
    main()
