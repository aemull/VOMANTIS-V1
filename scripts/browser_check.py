"""Read-only browser smoke test for a fresh installation.

Requires Playwright, Microsoft Edge, and an existing Manager/superuser account.
Set VOMANTIS_TEST_USERNAME and VOMANTIS_TEST_PASSWORD; no default credentials.
"""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get('VOMANTIS_TEST_URL', 'http://127.0.0.1:8000').rstrip('/')


def main():
    username = os.environ.get('VOMANTIS_TEST_USERNAME')
    password = os.environ.get('VOMANTIS_TEST_PASSWORD')
    if not username or not password:
        raise SystemExit('Set VOMANTIS_TEST_USERNAME dan VOMANTIS_TEST_PASSWORD ke akun Manager/superuser Anda.')
    output = ROOT / 'artifacts'
    output.mkdir(exist_ok=True)
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='msedge', headless=True)
        for label, viewport in [('desktop', {'width': 1440, 'height': 1050}),
                                ('mobile', {'width': 390, 'height': 844})]:
            context = browser.new_context(viewport=viewport, is_mobile=label == 'mobile',
                                          has_touch=label == 'mobile', device_scale_factor=1)
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('response', lambda response: errors.append(f'HTTP {response.status} {response.url}')
                    if response.status >= 400 else None)
            page.goto(BASE_URL + '/login/')
            page.get_by_label('Username', exact=True).fill(username)
            page.get_by_label('Password', exact=True).fill(password)
            page.get_by_role('button', name='Masuk ke workspace').click()
            page.wait_for_url(BASE_URL + '/')
            page.screenshot(path=str(output / f'browser-dashboard-{label}.png'), full_page=True)
            for route in ['/machines/', '/tickets/', '/schedule/', '/analytics/', '/data/']:
                page.goto(BASE_URL + route)
                assert page.locator('h1').count() == 1, route
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), route
            page.goto(BASE_URL + '/tickets/new/')
            page.get_by_role('button', name='Simpan perubahan').click()
            assert page.locator(':invalid').count() > 0, 'Required fields must block empty submission'
            if label == 'mobile':
                page.get_by_role('button', name='Buka menu').click()
                assert page.get_by_role('button', name='Buka menu').get_attribute('aria-expanded') == 'true'
            context.close()
        browser.close()
    if errors:
        raise AssertionError('\n'.join(errors))
    print('OK: desktop/mobile login, empty pages, navigation, required fields, no JS/HTTP errors.')


if __name__ == '__main__':
    main()
