"""只规范格式，不猜测型号、参数、单位、词间空格或表格结构。"""
import hashlib
import re
from collections import Counter

VERSION='conservative-whitespace-v1'
RULES={
    'normalize_line_ending':'CRLF/CR 等换行统一为 LF，保留页边界',
    'remove_bom':'移除文本中的 Unicode BOM，记录变化',
    'remove_control':'移除除制表/换行以外的 C0/DEL 控制字符',
    'normalize_space':'NBSP 与窄不换行空格转为普通空格',
    'collapse_horizontal_space':'行内连续普通空格/制表符合并为单空格',
    'trim_line_edges':'清理每行首尾的普通空格',
    'collapse_blank_lines':'连续空行最多保留两行；移除的行保留映射记录',
}


def text_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def clean_page(raw):
    output=[];mapping=[];counts=Counter();raw_pos=0;clean_pos=0;blank_count=0
    for number,piece in enumerate(raw.splitlines(keepends=True),1):
        body=piece.rstrip('\r\n\v\f\x85\u2028\u2029')
        ending=piece[len(body):]
        operations=[]
        if ending and ending!='\n':operations.append('normalize_line_ending')
        for name,pattern,replacement in [
            ('remove_bom','\ufeff',''),
            ('remove_control',r'[\x00-\x08\x0e-\x1f\x7f]',''),
            ('normalize_space',r'[\u00a0\u202f]',' '),
            ('collapse_horizontal_space',r'[ \t]+',' '),
        ]:
            changed=re.sub(pattern,replacement,body)
            if changed!=body:operations.append(name)
            body=changed
        trimmed=body.strip(' ')
        if trimmed!=body:operations.append('trim_line_edges')
        body=trimmed
        blank_count=blank_count+1 if not body else 0
        if blank_count>2:
            cleaned='';operations.append('collapse_blank_lines')
        else:
            cleaned=body+('\n' if ending else '')
        output.append(cleaned)
        mapping.append(dict(raw_line=number,raw_start=raw_pos,raw_end=raw_pos+len(piece),
                            clean_start=clean_pos,clean_end=clean_pos+len(cleaned),operations=operations))
        counts.update(operations);raw_pos+=len(piece);clean_pos+=len(cleaned)
    text=''.join(output)
    # 数字、非空白标点与字母等内容必须完整保留；控制字符/BOM 是唯一允许删除的非空白字符。
    def protected(value):return re.sub(r'\s|\ufeff|[\x00-\x08\x0e-\x1f\x7f]','',value)
    if protected(raw)!=protected(text):raise ValueError('清洗改变了受保护内容')
    return text,mapping,dict(counts)


def quality_flags(raw,cleaned):
    flags=[]
    chars=len(re.sub(r'\s','',cleaned))
    if not chars:flags.append('empty_or_image_page')
    elif chars<30:flags.append('sparse_text_page')
    if '\ufffd' in raw:flags.append('replacement_character')
    if re.search(r'[A-Za-z]{45,}',raw):flags.append('possible_fused_words')
    lines=[line.strip() for line in cleaned.splitlines() if line.strip()]
    if len(lines)>=20 and sum(len(s)<=3 for s in lines)/len(lines)>.6:
        flags.append('fragmented_short_lines')
    if len(lines)>=8 and sum(bool(re.search(r'\d',s)) for s in lines)/len(lines)>.65:
        flags.append('numeric_layout_review')
    return flags
