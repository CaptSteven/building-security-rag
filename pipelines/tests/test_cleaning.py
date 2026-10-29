import re
from pipelines.cleaning.rules import clean_page,quality_flags


def test_cleaning_preserves_specs_model_numbers_units_and_negation():
    raw='\ufeff  DS-2CD\t  12.5 V\r\n不支持\u00a0ONVIF; -30°C ~ +60°C\r\n\n\n\n'
    text,mapping,rules=clean_page(raw)
    assert text.startswith('DS-2CD 12.5 V\n不支持 ONVIF; -30°C ~ +60°C\n')
    assert mapping[0]['raw_start']==0 and mapping[-1]['raw_end']==len(raw)
    assert mapping[-1]['clean_end']==len(text)
    assert mapping[-1]['operations']==['collapse_blank_lines']
    assert 'normalize_line_ending' in rules and 'normalize_space' in rules
    for before,after in zip(mapping,mapping[1:]):
        assert before['raw_end']==after['raw_start'] and before['clean_end']==after['clean_start']


def test_cleaning_does_not_guess_words_or_remove_repeated_lines():
    raw='PoweroverEthernet\nAXIS M1\n065-LW\nManufacturer header\nManufacturer header\n'
    text,_,_=clean_page(raw)
    assert text==raw
    assert 'empty_or_image_page' in quality_flags('','')
    assert 'fragmented_short_lines' in quality_flags('A\n'*30,'A\n'*30)
    assert 'possible_fused_words' in quality_flags('A'*50,'A'*50)
    assert 'replacement_character' in quality_flags('x\ufffdy','x\ufffdy')


def test_jsonl_reader_preserves_unicode_line_separators_inside_text(tmp_path):
    import json
    from pipelines.jsonl import read_jsonl
    rows=[{'text':'英文\u2028中文\u0085内容\u2029结束'},{'text':'第二页'}]
    path=tmp_path/'sample.jsonl'
    path.write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows))
    assert list(read_jsonl(path))==rows
