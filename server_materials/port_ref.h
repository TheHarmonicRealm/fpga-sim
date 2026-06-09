#include <unordered_map>
#include <variant>
#include <string>
#include <iostream>
#include <optional>

#include "verilated.h"

QData make_mask(int width);

class PortReference {
    private:
        void* internal_pointer;
        QData mask;
        bool unread;
    public:
        int width;
        PortReference(void* data, unsigned int width);
        void set(QData value);
        std::optional<QData> poll();
};