"""
Dify API 调用封装
- 工作流1: 招标文件解析（parse）- 非流式，返回JSON
- 工作流2: 章节生成（generate）- 流式SSE
- 工作流3: 废标检查（check）- 非流式，返回JSON
"""
import os
import requests
from flask import current_app
from typing import Generator


def _auth_headers(api_key: str) -> dict:
    return {
        'Authorization': f'Bearer {api_key}',
    }


def _json_headers(api_key: str) -> dict:
    return {
        **_auth_headers(api_key),
        'Content-Type': 'application/json',
    }


def uploadFile(file_path: str, api_key: str) -> dict:
    """上传文件到 Dify，返回工作流文件变量对象"""
    base_url = current_app.config['DIFY_BASE_URL']
    timeout = current_app.config['DIFY_TIMEOUT']

    with open(file_path, 'rb') as file:
        resp = requests.post(
            f'{base_url}/files/upload',
            headers=_auth_headers(api_key),
            data={'user': 'bid-system'},
            files={
                'file': (os.path.basename(file_path), file, 'application/octet-stream')
            },
            timeout=timeout,
        )

    resp.raise_for_status()
    result = resp.json()
    return {
        'transfer_method': 'local_file',
        'upload_file_id': result['id'],
        'type': 'document',
    }


def run_parse_workflow(bid_text: str) -> dict:
    """
    调用招标文件解析工作流（Dify Workflow API，非流式）
    输入: bid_text - 招标文件纯文本
    输出: {'parsed_bid': str, 'format_template': str, 'risk_clauses': str, 'outline_json': str}
    """
    base_url = current_app.config['DIFY_BASE_URL']
    api_key = current_app.config['DIFY_API_KEY_PARSE']
    timeout = current_app.config['DIFY_TIMEOUT']

    payload = {
        'inputs': {
            'big_text': bid_text,
        },
        'response_mode': 'blocking',
        'user': 'bid-system',
    }

    resp = requests.post(
        f'{base_url}/workflows/run',
        headers=_json_headers(api_key),
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    result = resp.json()

    return result.get('data', {}).get('outputs', {})


def stream_generate_chapter(
    file_path: str,
    parsed_bid: str,
    chapter_title: str,
    chapter_structure: str,
    prompt_requirement: str,
) -> Generator[str, None, None]:
    """
    调用章节生成工作流（Dify Workflow API，流式SSE）
    逐块 yield SSE data 行字符串
    """
    base_url = current_app.config['DIFY_BASE_URL']
    api_key = current_app.config['DIFY_API_KEY_GENERATE']
    timeout = current_app.config['DIFY_TIMEOUT']
    file = uploadFile(file_path=file_path, api_key=api_key)

    payload = {
        'inputs': {
            'file': file,
            'parsed_bid': parsed_bid or '',
            'chapter_title': chapter_title,
            'chapter_structure': chapter_structure,
            'prompt_requirement': prompt_requirement or '',
        },
        'response_mode': 'streaming',
        'user': 'bid-system',
    }

    with requests.post(
        f'{base_url}/workflows/run',
        headers=_json_headers(api_key),
        json=payload,
        stream=True,
        timeout=timeout,
    ) as resp:
        if not resp.ok:
            try:
                detail = resp.json()
            except ValueError:
                detail = resp.text
            raise RuntimeError(f'Dify生成失败: {detail}')

        for line in resp.iter_lines():
            if line:
                decoded = line.decode('utf-8') if isinstance(line, bytes) else line
                yield decoded


def run_check_workflow(parsed_bid: str, risk_clauses: str, chapters_content: str) -> dict:
    """
    调用废标检查工作流（Dify Workflow API，非流式）
    输出: {'results': list, 'summary': dict}
    """
    base_url = current_app.config['DIFY_BASE_URL']
    api_key = current_app.config['DIFY_API_KEY_CHECK']
    timeout = current_app.config['DIFY_TIMEOUT']

    payload = {
        'inputs': {
            'parsed_bid': parsed_bid or '',
            'risk_clauses': risk_clauses or '',
            'chapters_content': chapters_content[:80000],
        },
        'response_mode': 'blocking',
        'user': 'bid-system',
    }

    resp = requests.post(
        f'{base_url}/workflows/run',
        headers=_json_headers(api_key),
        json=payload,
    )
    resp.raise_for_status()
    result = resp.json()
    outputs = result.get('data', {}).get('outputs', {})
    return outputs['results']
