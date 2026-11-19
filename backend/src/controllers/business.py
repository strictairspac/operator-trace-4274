from src.services import datasets,plans,traces,bundles
from src.services.audit import log
def save_dataset(data,user,item_id=None):
 row=datasets.save(data,item_id);log(user.email,'dataset.save',row['name']);return row
def save_plan(data,user,item_id=None):
 row=plans.save(data,item_id);log(user.email,'plan.save',row['name']);return row
def start_trace(data,user):
 row=traces.create(data);log(user.email,'trace.queue',row['name']);return row
def rerun_trace(item_id,user):
 row=traces.rerun(item_id);log(user.email,'trace.rerun',row['name']);return row
def export_bundle(data,user):
 bundle=bundles.export_bundle(data.ids);log(user.email,'bundle.export',f"{len(bundle['traces'])}条剖面 -> {bundle['bundle_id'][:12]}");return bundle
def import_bundle(payload,user):
 summary=bundles.import_bundle(payload);log(user.email,'bundle.import',f"包{summary['bundle_id'][:12]} 剖面{len(summary['traces'])}条");return summary
