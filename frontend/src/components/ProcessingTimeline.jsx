import { useEffect, useState } from "react";

export function ProcessingTimeline({ paper }) {
  const [currentStep, setCurrentStep] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);

  const steps = [
    {
      id: 'uploaded',
      title: 'Uploaded',
      description: 'File đã được nhận và lưu vào storage.',
      isCompleted: true,
      isActive: false
    },
    {
      id: 'parsing',
      title: 'PDF parsing',
      description: 'Trích xuất text preview, DOI và title candidate từ PDF.',
      isCompleted: paper.parseStatus === 'done' || paper.parseStatus === 'success',
      isActive: paper.parseStatus === 'processing' || (paper.status === 'parse_queued' && currentStep === 1),
      hasError: paper.parseStatus === 'failed'
    },
    {
      id: 'canonical',
      title: 'Canonical document',
      description: 'Liên kết paper hiện tại với canonical document nếu đã được nhận diện.',
      isCompleted: !!paper.canonicalDocumentId,
      isActive: false,
      hasError: false
    },
    {
      id: 'llm',
      title: 'LLM metadata chuyên biệt',
      description: 'Trích xuất metadata nâng cao kèm evidence khi pipeline giai đoạn sau được bật.',
      isCompleted: paper.hasLLMExtraction,
      isActive: false,
      hasError: false
    }
  ];

  useEffect(() => {
    // Determine current processing step
    if (paper.status === 'parse_queued' || paper.status === 'canonicalized' || paper.status === 'pending') {
      setIsProcessing(true);
      if (paper.parseStatus !== 'done' && paper.parseStatus !== 'success') {
        setCurrentStep(1);
      } else if (!paper.canonicalDocumentId) {
        setCurrentStep(2);
      } else if (!paper.hasLLMExtraction) {
        setCurrentStep(3);
      }
    } else {
      setIsProcessing(false);
    }
  }, [paper]);

  useEffect(() => {
    if (!isProcessing) return;

    const interval = setInterval(() => {
      setCurrentStep((prev) => {
        const nextStep = prev + 1;
        if (nextStep >= steps.length) {
          setIsProcessing(false);
          return prev;
        }
        return nextStep;
      });
    }, 3000); // Simulate processing time

    return () => clearInterval(interval);
  }, [isProcessing, steps.length]);

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
                      <path
                        d="M2.5 6L4.5 8L9.5 3"
                        stroke="white"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  )}
                  {hasError && (
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path
                        d="M3 3L9 9M9 3L3 9"
                        stroke="white"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  )}
                  {isActive && !isCompleted && !hasError && (
                    <div className="timeline-step__spinner" />
                  )}
                </div>
                {index < steps.length - 1 && (
                  <div className={`timeline-step__line timeline-step__line--horizontal ${isCompleted ? 'timeline-step__line--completed' : ''}`} />
                )}
              </div>
              <div className="timeline-step__content">
                <div className="timeline-step__title">{step.title}</div>
                <div className="timeline-step__description">{step.description}</div>
                {isActive && !isCompleted && !hasError && (
                  <div className="timeline-step__status">Đang xử lý...</div>
                )}
                {hasError && (
                  <div className="timeline-step__status timeline-step__status--error">
                    {paper.parseError || 'Xử lý thất bại'}
                  </div>
                )}
                {isCompleted && !hasError && (
                  <div className="timeline-step__status timeline-step__status--completed">
                    Hoàn thành
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
