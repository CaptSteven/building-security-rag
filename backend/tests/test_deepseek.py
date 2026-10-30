"""隔离的虚构证据与 MockTransport；不调用付费 API。"""
import copy
import json
import httpx
import pytest
from fastapi.testclient import TestClient
from security_rag import deepseek, library
from security_rag.deployed_app import create_app

KEY = 'fixture-deepseek-key-not-real'
EVIDENCE = {'citation':'S1','brand':'Test','model':'Fixture-CAM','title':'虚构测试资料',
            'page':1,'content':'Fictional fixture supports PoE.','sha256':'test-hash','quality_flags':[],
            'run_id':'fixture','asset_id':'A1','file_url':'/fixture'}


@pytest.fixture
def setup_client(tmp_path,monkeypatch):
    (tmp_path/'index.html').write_text('<h1>Fixture</h1>')
    result={'evidence':[EVIDENCE],'answer':None,'warnings':[],'mode':'keyword','text_source':'raw','indexed_documents':1,'indexed_pages':1,'note':'fixture'}
    monkeypatch.setattr(deepseek,'search',lambda body:copy.deepcopy(result))
    deepseek._calls.clear()
    client_type=httpx.Client
    seen=[]
    response={'choices':[{'finish_reason':'stop','message':{'content':'该虚构设备支持 PoE。[S1]'}}], 'usage':{'prompt_tokens':80,'completion_tokens':20,'total_tokens':100}}
    def handler(request):
        seen.append(request)
        return httpx.Response(200,json=response)
    monkeypatch.setattr(deepseek.httpx,'Client',lambda **kw:client_type(transport=httpx.MockTransport(handler),**kw))
    with TestClient(create_app(tmp_path)) as client:
        yield client,result,response,seen


def test_ask_fixed_destination_bounded_payload_and_audit(setup_client,caplog):
    client,_,_,seen=setup_client
    with caplog.at_level('INFO',logger='security_rag.generation'):
        response=client.post('/api/library/ask',json={'question':'PoE?'},headers={'X-DeepSeek-Key':KEY})
    assert response.status_code==200
    data=response.json();assert '[S1]' in data['answer'] and data['generation']['status']=='completed'
    assert data['generation']['usage']['total_tokens']==100
    assert str(seen[0].url)=='https://api.deepseek.com/chat/completions'
    assert seen[0].headers['authorization']==f'Bearer {KEY}'
    sent=json.loads(seen[0].content)
    assert sent['max_tokens']==1024 and sent['thinking']['type']=='disabled' and not sent['stream']
    assert '虚构测试资料' in sent['messages'][1]['content']
    assert KEY not in response.text and KEY not in caplog.text
    assert 'test-hash' in caplog.text and 'request_id' in caplog.text


def test_no_key_no_provider_call(setup_client):
    client,_,_,seen=setup_client
    assert client.post('/api/library/ask',json={'question':'PoE?'}).status_code==401
    assert not seen


def test_no_evidence_no_cost(setup_client):
    client,result,_,seen=setup_client;result['evidence']=[]
    response=client.post('/api/library/ask',json={'question':'PoE?'},headers={'X-DeepSeek-Key':KEY}).json()
    assert response['generation']['status']=='no_evidence' and response['answer'] is None and not seen


@pytest.mark.parametrize('answer,reason,error',[('无引用','stop','invalid_citations'),('引用错误 [S99]','stop','invalid_citations'),('半截 [S1]','length','incomplete_response')])
def test_bad_citations_or_incomplete_answers_hidden(setup_client,answer,reason,error):
    client,_,response,_=setup_client
    response['choices'][0]={'finish_reason':reason,'message':{'content':answer}}
    data=client.post('/api/library/ask',json={'question':'PoE?'},headers={'X-DeepSeek-Key':KEY}).json()
    assert data['answer'] is None and data['evidence'] and data['generation']['error_code']==error


@pytest.mark.parametrize('status,code',[(401,'invalid_key'),(402,'insufficient_balance'),(429,'upstream_rate_limit'),(503,'upstream_unavailable')])
def test_provider_failure_keeps_evidence_without_secret(setup_client,monkeypatch,status,code):
    client,_,_,_=setup_client
    def fail(*args,**kwargs):raise deepseek.DeepSeekError(code,'安全错误信息')
    monkeypatch.setattr(deepseek,'call_official',fail)
    data=client.post('/api/library/ask',json={'question':'PoE?'},headers={'X-DeepSeek-Key':KEY}).json()
    assert data['generation']['error_code']==code and data['evidence'] and data['warnings']
    assert KEY not in json.dumps(data)


def test_check_lists_models_without_generation(setup_client):
    client,_,response,seen=setup_client
    response.clear();response.update({'data':[{'id':'deepseek-flash'},{'id':'other'}]})
    data=client.post('/api/library/deepseek/check',headers={'X-DeepSeek-Key':KEY}).json()
    assert data['models']==['deepseek-flash'] and not data['generation_tested']
    assert seen[0].method=='GET' and seen[0].url.path=='/models'


def test_per_key_rate_limit_and_model_allowlist(setup_client):
    client,_,_,seen=setup_client
    headers={'X-DeepSeek-Key':KEY}
    for _ in range(6):assert client.post('/api/library/ask',json={'question':'PoE?'},headers=headers).status_code==200
    assert client.post('/api/library/ask',json={'question':'PoE?'},headers=headers).status_code==429
    assert len(seen)==6
    assert client.post('/api/library/ask',json={'question':'PoE?','model':'arbitrary-provider'},headers=headers).status_code==422


def test_official_error_mapping_and_timeout(monkeypatch):
    original=httpx.Client
    for status,code in [(401,'invalid_key'),(402,'insufficient_balance'),(429,'upstream_rate_limit'),(503,'upstream_unavailable')]:
        monkeypatch.setattr(deepseek.httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(lambda request:httpx.Response(status,text=KEY)),**kw))
        with pytest.raises(deepseek.DeepSeekError) as error:deepseek.call_official('GET','/models',KEY)
        assert error.value.code==code and KEY not in str(error.value)
    def timeout(request):raise httpx.ReadTimeout('secret '+KEY)
    monkeypatch.setattr(deepseek.httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(timeout),**kw))
    with pytest.raises(deepseek.DeepSeekError) as error:deepseek.call_official('GET','/models',KEY)
    assert error.value.code=='timeout' and KEY not in str(error.value)
