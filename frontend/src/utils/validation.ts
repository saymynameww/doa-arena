/**
 * 实验配置即时校验工具
 *
 * 提供前端校验逻辑，300ms 防抖调用后端校验
 */

export interface ValidationError {
  field: string;
  message: string;
  severity: 'error' | 'warning';
}

/**
 * 校验阵元数和信源数
 */
export const validateArrayAndSources = (
  arraySize: number,
  sourceCount: number
): ValidationError[] => {
  const errors: ValidationError[] = [];

  if (sourceCount >= arraySize) {
    errors.push({
      field: 'sourceCount',
      message: `信源数 K 必须小于阵元数 M（当前 K = ${sourceCount}, M = ${arraySize}）`,
      severity: 'error',
    });
  }

  if (arraySize < 2) {
    errors.push({
      field: 'arraySize',
      message: '阵元数至少为 2',
      severity: 'error',
    });
  }

  return errors;
};

/**
 * 校验快拍数
 */
export const validateSnapshots = (
  snapshots: number,
  arraySize: number
): ValidationError[] => {
  const errors: ValidationError[] = [];

  if (snapshots < arraySize) {
    errors.push({
      field: 'snapshots',
      message: `快拍数建议至少为阵元数的 2 倍（当前 ${snapshots}，建议 >= ${arraySize * 2}）`,
      severity: 'warning',
    });
  }

  if (snapshots < 10) {
    errors.push({
      field: 'snapshots',
      message: '快拍数过少，估计可能不准确',
      severity: 'warning',
    });
  }

  return errors;
};

/**
 * 校验试验次数
 */
export const validateTrials = (trials: number): ValidationError[] => {
  const errors: ValidationError[] = [];

  if (trials < 1) {
    errors.push({
      field: 'trials',
      message: '试验次数至少为 1',
      severity: 'error',
    });
  }

  if (trials < 20) {
    errors.push({
      field: 'trials',
      message: '试验次数较少，统计结果可能不稳定（建议 >= 50）',
      severity: 'warning',
    });
  }

  return errors;
};

/**
 * 校验扫描配置
 */
export const validateSweep = (
  sweepPath?: string,
  sweepValues?: number[]
): ValidationError[] => {
  const errors: ValidationError[] = [];

  if (!sweepPath) {
    errors.push({
      field: 'sweepPath',
      message: '未选择扫描变量',
      severity: 'error',
    });
  }

  if (!sweepValues || sweepValues.length === 0) {
    errors.push({
      field: 'sweepValues',
      message: '未设置扫描范围',
      severity: 'error',
    });
  } else if (sweepValues.length < 3) {
    errors.push({
      field: 'sweepValues',
      message: '扫描点数过少，建议至少 3 个点',
      severity: 'warning',
    });
  }

  return errors;
};

/**
 * 校验算法选择
 */
export const validateAlgorithms = (
  algorithms: any[]
): ValidationError[] => {
  const errors: ValidationError[] = [];

  if (algorithms.length === 0) {
    errors.push({
      field: 'algorithms',
      message: '至少选择一个算法',
      severity: 'error',
    });
  }

  return errors;
};

/**
 * 防抖函数
 */
export const debounce = <T extends (...args: any[]) => any>(
  func: T,
  delay: number
): ((...args: Parameters<T>) => void) => {
  let timeoutId: NodeJS.Timeout;

  return (...args: Parameters<T>) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => func(...args), delay);
  };
};
