export interface Document {cleaning_status?:string;cleaning_rules_version?:string;quality_flagged_pages?:number;initial_page?:number;run_id:string;asset_id:string;device_id:string;brand:string;model:string;category:string;kind:string;title:string;byte_size:number;page_count:number;extracted_pages:number;sha256:string;path:string;source_url:string;source_page:string;retrieved_at:string;extraction_status:string;review_status:string;file_url:string;status:string;error?:string;text_preview?:{page:number;text:string}[]}
export interface Summary {documents:number;pdf_pages:number;bytes:number;extracted_documents:number;extracted_pages:number;pending_documents:number;attention:number;categories:Record<string,number>;brands:Record<string,number>;kinds:Record<string,number>;groups:number;runs:{run_id:string;manifest_path:string}[];clean_documents:number;clean_pages:number;quality_flagged_pages:number;quality_flagged_documents:number;reviewed_documents:number;chunk_documents:number;vector_documents:number}
export interface Connections {deepseek_byok?:boolean;library:string;chat_configured:boolean;chat_model:string;embedding_configured:boolean;vector_status:string;authentication_enabled:boolean;note:string}
export interface Evidence {run_id:string;asset_id:string;title:string;model:string;brand:string;category:string;page:number;content:string;citation:string;source_url:string;source_page:string;file_url:string;sha256:string;quality_flags?:string[]}
export interface SearchResult {generation?:Generation;evidence:Evidence[];answer:string|null;warnings:string[];mode:string;text_source:"raw"|"cleaned";indexed_documents:number;indexed_pages:number;note:string}
export const kinds:Record<string,string>={datasheet:'参数表',installation:'安装指南',wiring:'接线图',manual:'技术手册',user_manual:'使用手册',comparison:'型号对照表'};
export const categories=['视频监控','门禁','对讲','入侵报警'];
let apiKey='';
export function setApiKey(key:string){apiKey=key;}
export async function request<T>(path:string,init:RequestInit={}):Promise<T>{
 const response=await fetch('/api/library'+path,{...init,headers:{...(init.body?{'Content-Type':'application/json'}:{}),...(apiKey?{'X-API-Key':apiKey}:{}),...init.headers}});
 if(!response.ok){let message=`请求失败 (${response.status})`;try {const data=await response.json();message=typeof data.detail==='string'?data.detail:message;}catch{}throw new Error(message);}
 return response.json();
}
export async function fileBlob(url:string):Promise<string>{const response=await fetch(url,{headers:apiKey?{'X-API-Key':apiKey}:{}});if(!response.ok)throw new Error(`文件读取失败 (${response.status})`);return URL.createObjectURL(await response.blob());}
export async function exportCsv(path='/documents.csv',filename='安保设备资料清单.csv'){const url=await fileBlob('/api/library'+path);const a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
export const size=(bytes:number)=>bytes>=1e6?`${(bytes/1e6).toFixed(1)} MB`:`${Math.round(bytes/1000)} KB`;
export const displayModel=(model:string)=>model.startsWith('family-')?'系列 / 集成资料（型号待核验）':model.replace(/^AXIS\s+/, '');

export const qualityNames:Record<string,string>={empty_or_image_page:'空白 / 图片页候选',sparse_text_page:'文本稀疏',possible_fused_words:'疑似单词黏连',fragmented_short_lines:'短行碎片',numeric_layout_review:'密集数字布局',replacement_character:'替换字符',extraction_error:'提取异常'};
export interface Processing {latest:null|{processing_run_id:string;rules_version:string;completed_at:string;summary:{documents:number;pages:number;flagged_pages:number;flagged_documents:number;changed_pages:number;raw_characters:number;clean_characters:number;human_reviewed_documents:number;quality_flag_counts:Record<string,number>};rules:{rules:Record<string,string>;forbidden:string[]}};examples:{run_id:string;asset_id:string;page:number;model:string;category:string;snippet:string;quality_flags:string[]}[]}

export type DeepSeekModel='deepseek-flash'|'deepseek-v4-pro';
export interface DeepSeekSession {ready:boolean;model:DeepSeekModel}
let deepSeekKey='';
export function configureDeepSeek(key:string){deepSeekKey=key.trim();}
export function deepSeekHeaders():Record<string,string>{return deepSeekKey?{'X-DeepSeek-Key':deepSeekKey}:{};}
export interface Generation {request_id:string;provider:string;model:string;status:'completed'|'failed'|'no_evidence';usage:Record<string,number>;cited_sources:string[];duration_ms:number;error_code:string|null}
export function downloadRecord(question:string,result:SearchResult){
 const blob=new Blob([JSON.stringify({exported_at:new Date().toISOString(),question,...result},null,2)],{type:'application/json'});
 const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`问答记录-${result.generation?.request_id||Date.now()}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
