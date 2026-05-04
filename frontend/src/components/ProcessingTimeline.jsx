import { useEffect, useState, useMemo } from "react";

export function ProcessingTimeline({ paper }) {
  const [currentStep, setCurrentStep] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);

  // ✅ Tách steps ra useMemo để ổn định reference
  const steps = useMemo(() => [
    {
      id: 'uploaded',
      title: 'Tải lên tài liệu',
      description: 'File đã được nhận và lưu vào storage.',
      isCompleted: true,
      isActive: false,
      hasError: false
    },
    {
      id: 'parsing',
      title: 'Phân tích tài liệu',
      description: 'Trích xuất text preview, DOI và title từ PDF.',
      isCompleted: 
        paper.processing_stage === 'enriching' ||
        paper.processing_stage === 'llm_extracting' ||
        paper.processing_status === 'parsed' ||
        paper.processing_status === 'processed' ||
        paper.processing_status === 'completed' ||  // thêm
        paper.processing_status === 'failed',
      isActive: paper.processing_stage === 'parsing',
      hasError: paper.processing_status === 'failed' && paper.processing_stage === 'parsing'
    },
    {
      id: 'enriching',
      title: 'Làm giàu tài liệu',
      description: 'Liên kết với canonical document và làm giàu metadata.',
      isCompleted: 
        paper.processing_stage === 'llm_extracting' ||
        paper.processing_status === 'completed' ||
        paper.processing_status === 'processed' ||
        paper.processing_status === 'enriched' ||
        paper.processing_status === 'failed',
      isActive: paper.processing_stage === 'enriching',
      hasError: paper.processing_status === 'failed' && paper.processing_stage === 'enriching'
    },
    {
      id: 'llm_extracting',
      title: 'Trích xuất LLM',
      description: 'Trích xuất metadata nâng cao bằng LLM.',
      isCompleted: 
        paper.processing_status === 'completed' ||
        paper.processing_stage === 'llm_extracted'  ,  
      isActive: paper.processing_stage === 'enriched',
      hasError: paper.processing_status === 'failed' && paper.processing_stage === 'llm_extracting'
    }
  ], [paper.processing_stage, paper.processing_status]); // chỉ depend vào các field thật sự cần

  useEffect(() => {
    if (!paper) return;

    if (paper.processing_status === 'failed') {
      setIsProcessing(false);
      const failedIndex = steps.findIndex(s => s.hasError);
      if (failedIndex !== -1) setCurrentStep(failedIndex);
      return;
    }

    if (paper.processing_status === 'completed') {
      setIsProcessing(false);
      setCurrentStep(steps.length); // tất cả hoàn thành
      return;
    }

    // Đang xử lý
    setIsProcessing(true);
    const activeIndex = steps.findIndex(step => step.isActive);
    if (activeIndex !== -1) {
      setCurrentStep(activeIndex);
    } else {
      // fallback: tìm step cuối cùng đã hoàn thành
      const lastCompleted = steps.findLastIndex(step => step.isCompleted);
      setCurrentStep(lastCompleted >= 0 ? lastCompleted + 1 : 0);
    }
  }, [paper, steps]); // giờ steps đã ổn định

  return (
    <div className="detail-section">
      <h3 className="detail-section__title">Luồng xử lý tài liệu</h3>
      <div className="processing-timeline processing-timeline--horizontal">
        {steps.map((step, index) => {
          const isActive = step.isActive || (isProcessing && index === currentStep);
          const isCompleted = step.isCompleted || (isProcessing && index < currentStep);
          const hasError = step.hasError;

          return (
            <div
              key={step.id}
              className={`timeline-step ${isCompleted ? 'timeline-step--completed' : ''} ${isActive ? 'timeline-step--active' : ''} ${hasError ? 'timeline-step--error' : ''}`}
            >
              <div className="timeline-step__indicator">
                <div className="timeline-step__dot">
                  {isCompleted && !hasError && (
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path d="M2.5 6L4.5 8L9.5 3" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  )}
                  {hasError && (
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path d="M3 3L9 9M9 3L3 9" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  )}
                  {isActive && !isCompleted && !hasError && <div className="timeline-step__spinner" />}
                </div>
                {index < steps.length - 1 && (
                  <div className={`timeline-step__line timeline-step__line--horizontal ${isCompleted ? 'timeline-step__line--completed' : ''}`} />
                )}
              </div>
              <div className="timeline-step__content">
                <div className="timeline-step__title">{step.title}</div>
                <div className="timeline-step__description">{step.description}</div>
                {isActive && !isCompleted && !hasError && <div className="timeline-step__status">Đang xử lý...</div>}
                {hasError && <div className="timeline-step__status timeline-step__status--error">{paper.processing_error || 'Xử lý thất bại'}</div>}
                {isCompleted && !hasError && <div className="timeline-step__status timeline-step__status--completed">Hoàn thành</div>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}