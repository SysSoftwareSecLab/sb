"""Review units cover the three finite parents' explicit behavioral obligations.
Each unit refers to the observed scenario, not all possible Python executions.
"""
COMMON={
 'SUPPORT_DEPARTURE':'每次释放须为本臂所持物体、位于声明支撑；随后同臂立即开始分离撤离，不产生正虚拟时间间隔。几何是否真正分离另见GEOMETRY。',
 'TERMINAL':'正常路径须在时限内完成全部物体/机械臂目标，双臂空手、资源OFF且无人占用、事件清空。专门注入的获取超时场景仅按公开fault_path_goal要求检查，不要求完成正常任务。',
 'GEOMETRY':'仅判断本次声明的固定方向平移AABB实体及禁碰对；依据完整几何重建与发现，不推断力学、全关节或所有可能路径的安全。',
}
SPECIFIC={
 'P01':{
  'BUFFER_OCCUPANCY_OWNER':'buffer_0/1为同一物理容量1缓存；进入和离开缓存接触期间须持有buffer_lock；每次提交释放时最多一个物体在缓存。',
  'BUFFER_EVENT_PROTOCOL':'ready_i只能在对应物体放入缓存且LEFT已撤离后发布；RIGHT取件前已等待对应ready。empty_0只能在第一物体放入目标且RIGHT撤离后发布；LEFT第二次进入前须等待并清除empty_0。ready须在对应带凭据搬运之后清除。',
  'BUFFER_RECEIPT':'RIGHT搬向target_i的调用须携带刚才等待的、仍活动的、匹配part_i的原始ready_i凭据。无凭据调用即使完成搬运也不合此义务。'},
 'P02':{
  'DUAL_RESOURCE_SPAN':'各臂按fixture→tool顺序获取；搬运到目标、释放及撤离期间同时持有两资源；撤离后按tool→fixture释放。判断实际调用/事件，不把“存在finally”当正确证据。',
  'TIMEOUT_CLEANUP':'若tool获取超时，已获取的fixture必须在该次退出前释放，且不能继续无双资源的目标搬运。未发生此超时则NA，不臆测未走过路径。'},
 'P03':{
  'REWORK_OBSERVATION':'每次检查区放置并撤离后由RIGHT签发本轮quality观测；LEFT检查区取件须使用本轮控制器签发、当前版本且值匹配的观测；每次放回检查区使版本递增。',
  'REWORK_BRANCH':'实际携物去向按本轮公开accept_by_pass决定：真则目标，假则返工再回检查区；最多两轮。已观察到错误分支即可V，未完成前缀不能凭缺少最终分支判C。'}
}
def for_parent(parent):return {**COMMON,**SPECIFIC[parent]}
