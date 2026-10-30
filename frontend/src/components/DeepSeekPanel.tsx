import {useState} from 'react';
import {KeyRound,LoaderCircle,ExternalLink} from 'lucide-react';
import {configureDeepSeek,deepSeekHeaders,request,type DeepSeekSession,type DeepSeekModel} from '../api';

export default function DeepSeekPanel({session,onChange}:{session:DeepSeekSession;onChange:(value:DeepSeekSession)=>void}){
 const [draft,setDraft]=useState('');
 const [model,setModel]=useState<DeepSeekModel>(session.model);
 const [testing,setTesting]=useState(false);
 const [message,setMessage]=useState('');
 const [error,setError]=useState('');
 function apply(){
  if(!draft.trim())return;
  configureDeepSeek(draft);onChange({ready:true,model});setDraft('');setError('');
  setMessage('已应用到本次页面会话，尚未验证连通性。');
 }
 function clear(){configureDeepSeek('');onChange({ready:false,model});setDraft('');setMessage('会话 Key 已清除。');setError('');}
 async function test(){
  setTesting(true);setMessage('');setError('');
  try{
   const result=await request<{models:string[];note:string}>('/deepseek/check',{method:'POST',headers:deepSeekHeaders()});
   setMessage(`${result.note} 可用模型：${result.models.join('、')}`);
  }catch(e){setError((e as Error).message);}finally{setTesting(false);}
 }
 return <section className="panel deepseek-panel"><div className="section-heading"><div><h2><KeyRound size={18}/>直接使用 DeepSeek</h2><p>使用自己的 API Key，按账户实际调用计费。</p></div><span className={'status '+(session.ready?'green':'gray')}>{session.ready?'本会话已配置':'未配置'}</span></div>
  <p>密钥只保存在当前页面内存中；调用时经本项目后端转发到 <strong>api.deepseek.com</strong>。不会写入浏览器存储、项目数据库或应用审计日志，刷新页面后需重新输入。</p>
  <form className="deepseek-form" onSubmit={e=>{e.preventDefault();apply();}}>
   <div><label htmlFor="deepseek-key" className="field-label">DeepSeek API Key</label><input id="deepseek-key" className="text-field" type="password" maxLength={256} autoComplete="off" spellCheck={false} value={draft} onChange={e=>setDraft(e.target.value)} placeholder={session.ready?'输入新 Key 可替换当前会话':'在此输入你的 DeepSeek Key'}/></div>
   <div><label htmlFor="deepseek-model" className="field-label">生成模型</label><select id="deepseek-model" className="text-field" value={model} onChange={e=>{const value=e.target.value as DeepSeekModel;setModel(value);onChange({...session,model:value});setMessage('');}}><option value="deepseek-flash">DeepSeek Flash</option><option value="deepseek-v4-pro">DeepSeek V4 Pro</option></select></div>
   <button type="submit" className="button primary" disabled={!draft.trim()||testing}>应用 Key</button>
  </form>
  <div className="deepseek-actions"><button className="button secondary" disabled={!session.ready||testing} onClick={()=>void test()}>{testing?<LoaderCircle size={16} className="spin"/>:null}检查连接</button><button className="text-button" disabled={!session.ready||testing} onClick={clear}>清除会话 Key</button><a className="text-button" href="https://platform.deepseek.com/api_keys" target="_blank" rel="noreferrer">获取官方 Key <ExternalLink size={14}/></a></div>
  <p className="small muted">检查连接只读取模型列表，不生成回答；连通成功不代表余额充足。应用后前往“检索与问答”，勾选“生成回答”。每次最多使用 6 条证据，输出最多 1,024 tokens；不自动重试。</p>
  {message?<p className="success-message" role="status">{message}</p>:null}{error?<p className="error" role="alert">{error}</p>:null}
 </section>;
}
