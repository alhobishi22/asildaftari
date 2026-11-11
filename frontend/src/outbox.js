export function uuid(){
 const bytes=crypto.getRandomValues(new Uint8Array(16));
 bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;
 const hex=Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');
 return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
}
export function enqueue(queue,entry){
 const existing=queue.find(q=>q.collection===entry.collection&&q.id===entry.id);
 const next=existing?queue.map(q=>q===existing?{...entry,method:q.method,body:{...q.body,...entry.body},failed:null}:q):[...queue,entry];
 if(next.length>300)throw new Error('ذاكرة الجهاز ممتلئة بعمليات لم تُرسل بعد — اتصل بالشبكة للمزامنة ثم أعد المحاولة');
 return next;
}
export function acknowledge(queue,entry){return queue.filter(q=>q.op!==entry.op).map(q=>q.collection===entry.collection&&q.id===entry.id?{...q,method:'PUT'}:q)}
