// Category: Pointer Errors (Success Case)
// Expected Result: Check for non-null before dereferencing, or handle null case safely

#include <iostream>

void process(int* ptr) {
    if (ptr != nullptr) {  // SUCCESS: Checked for NOT null before use
        *ptr = 0;
    } else {
        std::cout << "Pointer is null, skipping process" << std::endl;
    }
}

int main() {
    int* ptr = nullptr;
    process(ptr);
    
    return 0;
}
