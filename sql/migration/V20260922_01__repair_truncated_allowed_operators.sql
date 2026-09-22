-- 修复被 XSS HTML 过滤截断的比较符。仅回写仍非法、且以被转义的大于号开头的操作符。
UPDATE ts_tag_semantic
SET allowed_operators = '[">",">=","<","<=","between"]'
WHERE JSON_VALID(allowed_operators) = 0
  AND allowed_operators LIKE '["&gt;","&gt;=%';
