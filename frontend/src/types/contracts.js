/** @typedef {{id:number,name:string,sensors:object[],readings:object[],content_hash:string|null}} Dataset */
/** @typedef {{id:number,name:string,dataset_id:number,steps:object[],content_hash:string|null}} Plan */
/** @typedef {{id:number,name:string,status:'queued'|'running'|'completed'|'failed',result:object|null,source:'local'|'imported'}} Trace */
/** @typedef {{format:'operator-trace-bundle',version:number,bundle_id:string,datasets:object[],plans:object[],traces:object[]}} TraceBundle */
export {};
