export function enqueue(queue,entry){
 const existing=queue.find(q=>q.collection===entry.collection&&q.id===entry.id);
 const next=existing?queue.map(q=>q===existing?{...entry,method:q.method,body:{...q.body,...entry.body},failed:null}:q):[...queue,entry];
 if(next.length>300)throw new Error('ذاكرة الجهاز ممتلئة بعمليات لم تُرسل بعد — اتصل بالشبكة للمزامنة ثم أعد المحاولة');
 return next;
}
export function acknowledge(queue,entry){return queue.filter(q=>q.op!==entry.op).map(q=>q.collection===entry.collection&&q.id===entry.id?{...q,method:'PUT'}:q)}
